#!/usr/bin/env python3
"""spec_inspect.py — BitzSDD（sdd-core スキル）の構造検証・影響分析ツール（stdlib のみ）

使い方:
  python spec_inspect.py <repo-root>                 # 全検証 → .spec/inspection-report.md
  python spec_inspect.py --workspace plugins/* .     # モノリポ一括検証（クロスリファレンス解決）
  python spec_inspect.py <repo-root> --check-only    # レポートを書き込まず全検証
  python spec_inspect.py <repo-root> --impact FR-012 # 変更影響分析（stale候補の列挙）
  python spec_inspect.py <repo-root> --impact-docs docs/03_設計仕様/アーキテクチャ.md
                                                     # docs変更の影響要件（derived_from 逆引き）
"""
import argparse
import base64
import binascii
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_labels import status_label  # noqa: E402
from spec_trace import build_task_index  # noqa: E402

ID_RE = re.compile(r"\b(?:[A-Z0-9]{2,4}-)?(?:FR|NFR|CON|DSC|DSN|INF|REV|TSK)-\d{3}\b")
ISSUE_ID_RE = re.compile(r"\bSI-[A-Z0-9]{2,4}-\d{3}\b")
DOCS_REF_RE = re.compile(r"(docs/[^\s@]+)(?:@([0-9a-fA-F]{7,40}))?")
PREFIXES = ("FR", "NFR", "CON", "DSC", "DSN", "INF", "REV", "TSK")
STATUSES = {"draft", "approved", "implementing", "verified", "promoted", "deprecated", "in-review", "active", "revised", "archived", "pending", "complete", "superseded"}
VMETHODS = {"pbt", "example-test", "unit-test", "benchmark", "sast", "dep-audit", "load-test", "manual-check"}
ACTIVE = {"approved", "implementing", "verified", "promoted"}  # 検証対象ステータス
ORPHAN_STATUSES = {"implementing", "verified", "promoted"}


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r"^(\w[\w-]*):\s*(.*?)\s*(?:#.*)?$", line)
            if kv:
                val = kv.group(2).strip()
                # クォート除去（docs_inspect / sdd_report と同挙動）
                if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                    val = val[1:-1]
                fm[kv.group(1)] = val
    return fm


def load_requirements(root: Path):
    reqs = {}
    problems = []
    dirs_to_scan = [
        root / ".spec" / "requirements",
        root / ".spec" / "discovery",
        root / ".spec" / "design",
        root / ".spec" / "design" / "infra",
        root / ".spec" / "reviews"
    ]
    for d in dirs_to_scan:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            if f.name.startswith("_") or f.name in ("domains.md",):
                continue
            text = f.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            rid = fm.get("id", "")
            if not rid:
                problems.append(f"[構造] {f.relative_to(root)}: frontmatter に id がない")
                continue
            if d.name == "requirements" and f.stem != rid:
                problems.append(f"[構造] {f.relative_to(root)}: ファイル名と id ({rid}) が不一致")
            prefix_part = rid.split("-")
            core_prefix = prefix_part[1] if len(prefix_part) > 2 else prefix_part[0]
            if core_prefix not in PREFIXES:
                problems.append(f"[構造] {rid}: プレフィックスが正規外")
            if rid in reqs:
                problems.append(f"[重複] {rid}: IDが重複している")
            reqs[rid] = {"fm": fm, "text": text, "path": f}
    return reqs, problems


def load_spec_issues(root: Path):
    """spec-issues/*.md の frontmatter を集める（委託チェック用。SDD-FR-132）。

    spec-issue は status 語彙（open/accepted 等）と ID 書式が要件と異なるため、
    load_requirements のレジストリには混ぜず専用に読む（誤検知の防止）。
    """
    issues = {}
    d = root / ".spec" / "spec-issues"
    if not d.exists():
        return issues
    for f in sorted(d.glob("*.md")):
        fm = parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
        iid = fm.get("id") or f.stem
        issues[iid] = {"fm": fm, "path": f}
    return issues


def build_delegation_context(workspaces):
    """委託チェック用の横断レジストリを構築する（SDD-FR-132）。

    返り値: (known_ids, origin_by_id)
      known_ids   : 全 ws の 要件 ∪ spec-issue ∪ タスク（ファイル名 stem）の ID 集合
      origin_by_id: ID → frontmatter origin: テキスト（要件・spec-issue。双方向言及の検査用）
    """
    known_ids = set()
    origin_by_id = {}
    for w in workspaces:
        reqs, _ = load_requirements(w)
        for rid, r in reqs.items():
            known_ids.add(rid)
            origin_by_id[rid] = r["fm"].get("origin", "")
        for iid, issue in load_spec_issues(w).items():
            known_ids.add(iid)
            origin_by_id[iid] = issue["fm"].get("origin", "")
        tasks_dir = w / ".spec" / "tasks"
        if tasks_dir.exists():
            known_ids.update(f.stem for f in tasks_dir.rglob("*.md"))
    return known_ids, origin_by_id


def check_delegations(root: Path, known_ids: set, origin_by_id: dict) -> list:
    """spec-issue の delegated_to（`<ws>:<ID>` カンマ区切り）を横断検証する（SDD-FR-132）。

    - ID 部が known_ids に実在すること（`<ws>:` 修飾部は人間向け情報として検証しない）
    - 委託先 frontmatter の origin: テキストに委託元 spec-issue ID への言及があること
      （注記付きの自由記述を容認するため「言及」ベースで突合する。CORE-FR-012 と同じ流儀）
    origin / delegated_to を持たない既存 spec-issue はチェック対象外（後方互換）。
    """
    problems = []
    for iid, issue in load_spec_issues(root).items():
        raw = issue["fm"].get("delegated_to", "")
        if not raw:
            continue
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry:
                continue
            target = entry.rsplit(":", 1)[-1].strip()
            if target not in known_ids:
                problems.append(f"[委託] {iid}: delegated_to の {entry} が実在しない（リンク切れ）")
            elif iid not in origin_by_id.get(target, ""):
                problems.append(
                    f"[委託] {iid}: 委託先 {target} の origin: に {iid} への言及がない（双方向リンク欠如）")
    return problems


def load_domains(req_dir: Path):
    dom_file = req_dir / "domains.md"
    if not dom_file.exists():
        return None
    codes = set()
    for line in dom_file.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*([a-z][\w-]*)\s*\|", line)
        if m and m.group(1) != "code":
            codes.add(m.group(1))
    return codes


def load_forbidden_words(req_dir: Path):
    lint_file = req_dir / "_lint-rules.md"
    if not lint_file.exists():
        return []
    text = lint_file.read_text(encoding="utf-8")
    m = re.search(r"## 禁止語.*?\n(.+?)(?:\n##|\Z)", text, re.S)
    if not m:
        return []
    words = []
    for token in re.split(r"[,、\n]", m.group(1)):
        token = token.strip()
        if token and not token.startswith("#"):
            words.append(re.sub(r"\(.*?\)", "", token).strip())
    return [w for w in words if w]


def scan_refs(root: Path, subdirs, exclude_names=()):
    """subdirs 内の md/コード類から 要件ID → 参照元ファイル一覧 を集める"""
    refs = {}
    for sub in subdirs:
        d = root / sub
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file() or f.name in exclude_names:
                continue
            if f.suffix not in {".md", ".py", ".ts", ".js", ".rs", ".go", ".java", ".yaml", ".yml", ".toml", ".txt"}:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for rid in set(ID_RE.findall(text)):
                if rid == f.stem:
                    # ファイル自身の ID は自己言及であって参照ではない（タスクが自分の ID を名乗れるように）
                    continue
                refs.setdefault(rid, []).append(str(f.relative_to(root)))
    return refs


_sha_cache = {}


def git_head_sha(root: Path, rel_path: str):
    """rel_path を最後に変更したコミットSHA。git 不在/リポジトリ外/未コミットは None（縮退）"""
    if rel_path in _sha_cache:
        return _sha_cache[rel_path]
    sha = None
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%H", "--", rel_path],
                             cwd=root, capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            sha = out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        sha = None
    _sha_cache[rel_path] = sha
    return sha


def derived_docs_ref(fm: dict):
    """frontmatter の derived_from から (docsパス, 記録SHA) を取り出す"""
    m = DOCS_REF_RE.search(fm.get("derived_from", ""))
    return (m.group(1), m.group(2)) if m else (None, None)


def sha_matches(a: str, b: str) -> bool:
    return a.startswith(b) or b.startswith(a)


def implements_map(root: Path):
    """tasks/ の implements: 行から 要件ID → タスクファイル を集める"""
    impl = {}
    tasks = root / ".spec" / "tasks"
    if not tasks.exists():
        return impl
    for f in tasks.rglob("*.md"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if re.search(r"implements\s*:", line):
                for rid in ID_RE.findall(line):
                    impl.setdefault(rid, []).append(str(f.relative_to(root)))
    return impl


def local_task_statuses(root: Path) -> dict[str, list[tuple[str, str]]]:
    """Shared spec_trace index projected for inspect diagnostics (SDD-FR-143)."""
    result = {}
    for (workspace, requirement_id), bindings in build_task_index(root).items():
        if workspace != root.resolve():
            continue
        result[requirement_id] = [
            (str(binding.path.relative_to(root)), binding.status) for binding in bindings
        ]
    return result


def check_state_events(root: Path) -> list[str]:
    """Validate structured STATE events and incomplete transactions (SDD-FR-143)."""
    problems = []
    spec_dir = root / ".spec"
    journals = sorted((spec_dir / ".transactions").glob("*.json")) \
        if (spec_dir / ".transactions").exists() else []
    if journals:
        problems.append(
            "[transaction] incomplete-transaction: "
            + ", ".join(path.stem for path in journals)
        )
    if (spec_dir / ".mutation-lock").exists():
        problems.append("[transaction] mutation lockが残っています")

    state = spec_dir / "STATE.md"
    if not state.exists():
        return problems
    lines = state.read_text(encoding="utf-8", errors="replace").splitlines()
    event_ids = set()
    events_by_artifact: dict[str, list[dict]] = {}
    for index, line in enumerate(lines):
        marker = re.fullmatch(r"<!-- sdd-event:([A-Za-z0-9+/=]+) -->", line)
        if not marker:
            if line.startswith("<!-- sdd-event:"):
                problems.append(f"[audit] audit-corruption: STATE line {index + 1}: marker format")
            continue
        if index == 0 or not lines[index - 1].startswith("- "):
            problems.append("[audit] structured STATE eventに直前の表示行がありません")
        encoded = marker.group(1)
        try:
            payload = base64.b64decode(encoded, validate=True)
            if base64.b64encode(payload).decode("ascii") != encoded:
                raise ValueError("non-canonical base64")
            event = json.loads(payload)
            canonical = json.dumps(
                event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            if canonical != payload:
                raise ValueError("non-canonical JSON")
            required = {
                "schema_version", "event_id", "timestamp", "path", "artifact_id",
                "old", "new", "provenance", "artifact_before_hash", "artifact_after_hash",
            }
            if event.get("schema_version") != 1 or not required.issubset(event):
                raise ValueError("schema mismatch")
            if (
                not all(isinstance(event.get(key), str) and event[key]
                        for key in ("event_id", "path", "artifact_id", "old", "new"))
                or not isinstance(event.get("provenance"), dict)
                or not re.fullmatch(r"[0-9a-f]{64}", event.get("artifact_before_hash", ""))
                or not re.fullmatch(r"[0-9a-f]{64}", event.get("artifact_after_hash", ""))
            ):
                raise ValueError("schema type mismatch")
            event_id = event["event_id"]
            if event_id in event_ids:
                raise ValueError("duplicate event_id")
            event_ids.add(event_id)
            display = lines[index - 1] if index else ""
            transition = f"{event['artifact_id']}: {event['old']} → {event['new']}"
            if transition not in display:
                raise ValueError("display line mismatch")
            artifact_path = (root / event["path"]).resolve()
            if not artifact_path.is_relative_to(root.resolve()):
                raise ValueError("artifact path escapes workspace")
            events_by_artifact.setdefault(event["artifact_id"], []).append(event)
        except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
            problems.append(f"[audit] audit-corruption: STATE line {index + 1}: {exc}")

    for artifact_id, events in events_by_artifact.items():
        for previous, current in zip(events, events[1:]):
            if previous["new"] != current["old"]:
                problems.append(
                    f"[audit] audit-corruption: {artifact_id}の遷移連鎖が不正: "
                    f"{previous['new']} != {current['old']}"
                )
        last = events[-1]
        artifact_path = (root / last["path"]).resolve()
        try:
            current_status = parse_frontmatter(
                artifact_path.read_text(encoding="utf-8")
            ).get("status", "")
        except OSError:
            current_status = ""
        if current_status != last["new"]:
            problems.append(
                f"[audit] audit-corruption: {artifact_id}の現status "
                f"({current_status or 'missing'}) が最終event ({last['new']}) と不一致"
            )
    return problems


def integration_preflight(root: Path, target_ref: str) -> tuple[bool, str]:
    """Bind ID collision preflight to an exact target commit SHA (SDD-FR-144)."""
    try:
        top_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        sha_result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{target_ref}^{{commit}}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if top_result.returncode or sha_result.returncode:
            return False, "integration-preflight: target SHAを証明できません"
        repo = Path(top_result.stdout.strip()).resolve()
        target_sha = sha_result.stdout.strip()
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", target_sha, "HEAD"],
            cwd=repo,
            capture_output=True,
            timeout=10,
        )
        if ancestry.returncode != 0:
            return False, f"integration-preflight: target_sha={target_sha} はHEADのancestorではありません"

        workspace_rel = root.resolve().relative_to(repo)
        scope = str(workspace_rel / ".spec") if str(workspace_rel) != "." else ".spec"
        tree = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", target_sha, "--", scope],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
        target_id_paths: dict[str, set[str]] = {}
        target_accepted_issues = set()
        target_origin_issues = set()
        target_paths = set(tree.stdout.splitlines())
        for relpath in target_paths:
            shown = subprocess.run(
                ["git", "show", f"{target_sha}:{relpath}"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if shown.returncode == 0:
                target_meta = parse_frontmatter(shown.stdout)
                if "/spec-issues/" in f"/{relpath}":
                    if target_meta.get("status") == "accepted":
                        target_accepted_issues.add(target_meta.get("id") or Path(relpath).stem)
                else:
                    target_origin_issues.update(
                        ISSUE_ID_RE.findall(target_meta.get("origin", ""))
                    )
                if target_meta.get("id"):
                    target_id_paths.setdefault(target_meta["id"], set()).add(relpath)
                elif "/tasks/" in f"/{relpath}":
                    target_id_paths.setdefault(Path(relpath).stem, set()).add(relpath)

        collisions = []
        for directory in ("requirements", "design", "reviews", "tasks"):
            current_dir = root / ".spec" / directory
            if not current_dir.exists():
                continue
            for path in current_dir.rglob("*.md"):
                relpath = str(path.resolve().relative_to(repo))
                if relpath in target_paths:
                    continue
                meta = parse_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
                artifact_id = meta.get("id") or path.stem
                target_holders = target_id_paths.get(artifact_id, set())
                target_id_still_present = False
                for holder in target_holders:
                    current_holder = repo / holder
                    if not current_holder.exists():
                        continue
                    holder_meta = parse_frontmatter(
                        current_holder.read_text(encoding="utf-8", errors="ignore")
                    )
                    current_holder_id = holder_meta.get("id")
                    if not current_holder_id and "/tasks/" in f"/{holder}":
                        current_holder_id = current_holder.stem
                    if current_holder_id == artifact_id:
                        target_id_still_present = True
                        break
                if target_id_still_present:
                    collisions.append(f"{artifact_id} ({relpath})")
        protected_origins = target_accepted_issues & target_origin_issues
        current_origin_issues = set()
        for directory in ("requirements", "design", "reviews", "discovery"):
            current_dir = root / ".spec" / directory
            if not current_dir.exists():
                continue
            for path in current_dir.rglob("*.md"):
                meta = parse_frontmatter(
                    path.read_text(encoding="utf-8", errors="ignore")
                )
                current_origin_issues.update(
                    ISSUE_ID_RE.findall(meta.get("origin", ""))
                )
        missing_origins = sorted(protected_origins - current_origin_issues)
        failures = []
        if collisions:
            failures.append("ID衝突: " + ", ".join(sorted(collisions)))
        if missing_origins:
            failures.append("accepted issueのorigin成果物消失: " + ", ".join(missing_origins))
        if failures:
            return False, (
                f"integration-preflight: target_sha={target_sha} "
                + " / ".join(failures)
            )
        return True, f"integration-preflight: PASS target_sha={target_sha}"
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return False, f"integration-preflight: target SHAを証明できません: {exc}"


def inspect(root: Path, global_reqs: dict = None, delegation_ctx: tuple = None) -> str:
    req_dir = root / ".spec" / "requirements"
    if not req_dir.exists():
        return f"ERROR: {req_dir} が存在しません（BitzSDD レイアウト未初期化）"
    reqs, problems = load_requirements(root)
    if global_reqs is None:
        global_reqs = reqs
    if delegation_ctx is None:
        delegation_ctx = build_delegation_context([root])
    problems += check_delegations(root, *delegation_ctx)
    domains = load_domains(req_dir)
    forbidden = load_forbidden_words(req_dir)
    impl = implements_map(root)
    task_statuses = local_task_statuses(root)
    all_refs = scan_refs(root, [".spec/specs", ".spec/tasks", "tests", "test", "src"],
                         exclude_names=("inspection-report.md",))
    problems += check_state_events(root)

    for rid, r in reqs.items():
        fm = r["fm"]
        st = fm.get("status", "")
        if st not in STATUSES:
            problems.append(f"[frontmatter] {rid}: status '{st}' は語彙外")
        prefix_part = rid.split("-")
        core_prefix = prefix_part[1] if len(prefix_part) > 2 else prefix_part[0]
        if core_prefix in ("FR", "NFR", "CON"):
            if st in ACTIVE and fm.get("verification_method", "") not in VMETHODS:
                problems.append(f"[frontmatter] {rid}: verification_method が未記入/語彙外（approved 以降は必須）")
            if st == "deprecated" and not fm.get("superseded_by") and "廃止" not in r["text"]:
                problems.append(f"[frontmatter] {rid}: deprecated だが superseded_by が空（純粋廃止なら本文に理由を明記）")
            if domains is not None and fm.get("domain") and fm["domain"] not in domains:
                problems.append(f"[domain] {rid}: '{fm['domain']}' は domains.md 未登録")
            body = re.sub(r"^---.*?---", "", r["text"], flags=re.S)
            for w in forbidden:
                if w and w in body:
                    problems.append(f"[lint] {rid}: 禁止語『{w}』（測定不能）を含む — 数値/閾値へ書き換え")
            ears_clause = ""
            for line in body.splitlines() + [""]:
                stripped = line.strip()
                if stripped.startswith("- WHEN"):
                    if ears_clause and "SHALL" not in ears_clause:
                        problems.append(
                            f"[lint] {rid}: EARS不完全（WHEN 節に SHALL がない）"
                        )
                    ears_clause = stripped[2:].strip()
                elif ears_clause and (
                    not stripped
                    or stripped.startswith("- ")
                    or stripped.startswith("#")
                ):
                    if "SHALL" not in ears_clause:
                        problems.append(
                            f"[lint] {rid}: EARS不完全（WHEN 節に SHALL がない）"
                        )
                    ears_clause = ""
                elif ears_clause:
                    ears_clause += " " + stripped
            if st in {"verified", "promoted"}:
                bindings = task_statuses.get(rid, [])
                incomplete = [f"{path} ({status or 'missing'})"
                              for path, status in bindings if status != "done"]
                if not bindings:
                    problems.append(f"[trace] {rid}: verified/promotedだがlocal taskがない")
                elif incomplete:
                    problems.append(
                        f"[trace] {rid}: verified/promotedだが未完了local taskがある: "
                        + ", ".join(incomplete)
                    )

    # タスク ID（.spec/tasks/ のファイル名 stem）は既知 ID として幽霊判定から除外する
    # （depends_on / specs からのタスク参照を許すため。成果物レジストリには登録しない — SI-CORE-003）
    tasks_dir = root / ".spec" / "tasks"
    task_ids = {f.stem for f in tasks_dir.rglob("*.md")} if tasks_dir.exists() else set()
    ghosts = {rid: srcs for rid, srcs in all_refs.items()
              if rid not in global_reqs and rid not in task_ids}
    waiting = [rid for rid, r in reqs.items()
               if r["fm"].get("status") == "approved" and (rid.split("-")[1] if len(rid.split("-"))>2 else rid.split("-")[0]) in ("FR", "NFR", "CON") and rid not in impl]
    orphans = [rid for rid, r in reqs.items()
               if r["fm"].get("status") in ORPHAN_STATUSES and (rid.split("-")[1] if len(rid.split("-"))>2 else rid.split("-")[0]) in ("FR", "NFR", "CON") and rid not in impl]
    untested = [rid for rid, r in reqs.items()
                if r["fm"].get("status") in ACTIVE and (rid.split("-")[1] if len(rid.split("-"))>2 else rid.split("-")[0]) in ("FR", "NFR", "CON")
                and not any(s.startswith(("tests", "test", "src")) for s in all_refs.get(rid, []))]

    lines = [f"# inspection-report.md ({date.today().isoformat()})", ""]
    lines.append(f"成果物数: {len(reqs)} / 問題: {len(problems)} / 幽霊参照: {len(ghosts)} / 実装待ち: {len(waiting)} / 孤児要件: {len(orphans)}")
    lines.append("")
    lines.append("## 問題一覧")
    lines += [f"- {p}" for p in problems] or ["- なし ✅"]
    lines.append("")
    lines.append("## 幽霊参照（存在しないIDへの参照）")
    lines += [f"- {rid} ← {', '.join(srcs)}" for rid, srcs in sorted(ghosts.items())] or ["- なし ✅"]
    lines.append("")
    lines.append("## 実装待ち要件（approved だが implements するタスクがない — WARN）")
    lines += [f"- {rid}" for rid in waiting] or ["- なし ✅"]
    lines.append("")
    lines.append("## 孤児要件（implementing以降なのに implements するタスクがない）")
    lines += [f"- {rid}" for rid in orphans] or ["- なし ✅"]
    lines.append("")
    lines.append("## テスト/実装からの参照がない要件（approved以降）")
    lines += [f"- {rid}" for rid in untested] or ["- なし ✅"]
    lines.append("")
    diverged = []
    for rid, r in sorted(reqs.items()):
        path, recorded = derived_docs_ref(r["fm"])
        if not path or not recorded:
            continue
        current = git_head_sha(root, path)
        if current and not sha_matches(current, recorded):
            diverged.append(f"{rid} ← {path} ({recorded[:7]} → {current[:7]})")
    lines.append("## docs 乖離（派生元 docs が派生後に変更された要件 — stale 候補）")
    lines.append("※ 乖離は候補提示のみ。stale 付与は references/lifecycle.md の再伝播プロトコル（判定パス→人間確認）を経ること")
    lines += [f"- {d}" for d in diverged] or ["- なし ✅"]
    lines.append("")
    lines.append("## Traceability Matrix")
    lines.append("| ID | status | domain | v-method | tasks | 参照元数 |")
    lines.append("|----|--------|--------|----------|-------|----------|")
    for rid, r in sorted(reqs.items()):
        fm = r["fm"]
        lines.append(f"| {rid} | {status_label('requirement', fm.get('status',''))} | {fm.get('domain','')} | "
                     f"{fm.get('verification_method','')} | {len(impl.get(rid, []))} | {len(all_refs.get(rid, []))} |")
    ok = not problems and not ghosts and not orphans
    lines.append("")
    lines.append("**判定: " + ("PASS ✅" if ok else "FAIL ❌（上記を解消するまで verified に進めない）") + "**")
    return "\n".join(lines)


def impact(root: Path, target: str, global_reqs: dict = None) -> str:
    reqs, _ = load_requirements(root)
    if global_reqs is None:
        global_reqs = reqs
    if target not in global_reqs:
        return f"ERROR: {target} は登録簿に存在しません"
    ver = global_reqs[target]["fm"].get("version", "?")
    all_refs = scan_refs(root, [".spec/specs", ".spec/tasks", "tests", "test", "src", "docs"],
                         exclude_names=("inspection-report.md",))
    hits = sorted(set(all_refs.get(target, [])))
    lines = [f"# impact: {target}@{ver}", "",
             f"依存成果物: {len(hits)} 件。各成果物に `stale: {target}@{ver}` を付与し、更新済みから外すこと。", ""]
    lines += [f"- [ ] {h}" for h in hits] or ["- 依存成果物なし"]
    supers = [rid for rid, r in reqs.items() if r["fm"].get("supersedes") == target]
    if supers:
        lines.append(f"\n後継要件: {', '.join(supers)}")
    return "\n".join(lines)


def impact_docs(root: Path, target: str, global_reqs: dict = None) -> str:
    """docs/ 文書の変更が影響する要件を derived_from の逆引きで列挙する（再伝播プロトコルの候補列挙）"""
    req_dir = root / ".spec" / "requirements"
    if not req_dir.exists():
        return f"ERROR: {req_dir} が存在しません（BitzSDD レイアウト未初期化）"
    reqs, _ = load_requirements(root)
    if global_reqs is None:
        global_reqs = reqs
    target = target.strip().lstrip("./")
    current = git_head_sha(root, target)
    rows = []
    for rid, r in sorted(reqs.items()):
        path, recorded = derived_docs_ref(r["fm"])
        if path != target:
            continue
        if current is None:
            state = "SHA比較不可（git 不在/未コミット）— 内容を目視確認"
        elif recorded is None:
            state = "派生時SHA未記録 — 内容を目視確認"
        elif sha_matches(current, recorded):
            state = "一致（派生後の変更なし）"
        else:
            state = f"乖離 {recorded[:7]} → {current[:7]} — stale 候補"
        rows.append(f"- [ ] {rid} (status: {status_label('requirement', r['fm'].get('status', ''))}) — {state}")
    lines = [f"# impact-docs: {target}", ""]
    if current:
        lines.append(f"現行コミット: {current[:12]}")
    lines.append(f"派生要件: {len(rows)} 件。乖離のあるものは references/lifecycle.md の"
                 "再伝播プロトコル（判定パス→人間確認→最小再実行）に従い stale を付与すること。")
    lines.append("")
    lines += rows or ["- この文書から派生した要件はありません"]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="BitzSDD inspection tool")
    parser.add_argument("roots", nargs="*", default=["."], help="Workspace roots")
    parser.add_argument("--workspace", nargs="+", help="Explicitly specify workspace roots (overrides positional roots)")
    parser.add_argument("--check-only", action="store_true",
                        help="Run inspection without creating or updating inspection-report.md")
    parser.add_argument("--impact", help="ID for impact analysis")
    parser.add_argument("--impact-docs", help="docs path for impact analysis")
    parser.add_argument("--target-ref",
                        help="integration preflightを束縛するtarget ref（SDD-FR-144）")
    args = parser.parse_args()

    workspaces = [Path(p).resolve() for p in (args.workspace if args.workspace else args.roots)]
    workspaces = [w for w in workspaces if w.is_dir() and (w / ".spec").exists()]
    
    if not workspaces:
        print("ERROR: No valid BitzSDD workspaces found.")
        sys.exit(1)

    global_reqs = {}
    for w in workspaces:
        reqs, _ = load_requirements(w)
        global_reqs.update(reqs)
    delegation_ctx = build_delegation_context(workspaces)

    has_error = False
    if args.target_ref:
        for workspace in workspaces:
            passed, message = integration_preflight(workspace, args.target_ref)
            print(message)
            if not passed:
                has_error = True
    for w in workspaces:
        if len(workspaces) > 1:
            print(f"=== Workspace: {w.name} ===")
            
        if args.impact_docs:
            print(impact_docs(w, args.impact_docs, global_reqs))
        elif args.impact:
            print(impact(w, args.impact, global_reqs))
        else:
            report = inspect(w, global_reqs, delegation_ctx)
            out = w / ".spec" / "inspection-report.md"
            if not report.startswith("ERROR"):
                if not args.check_only:
                    out.write_text(report + "\n", encoding="utf-8")
                print(report)
                if "FAIL ❌" in report:
                    has_error = True
            else:
                print(report)
                has_error = True
                
        if len(workspaces) > 1:
            print()

    if has_error:
        sys.exit(1)

if __name__ == "__main__":
    main()
