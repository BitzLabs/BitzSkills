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
# 権限マトリクス上エージェント単独では到達できない状態（SDD-FR-143 / SI-SDD-026）。
# 到達の証跡が無い＝CLIを迂回した規律違反と断定できる範囲に限定する。
HUMAN_ONLY_STATES = {
    "approved", "promoted", "deprecated",       # requirement
    "accepted", "rejected", "superseded",       # spec-issue
}
# 参照走査の拡張子（SDD-FR-147）。実装ディレクトリはコードだけを「実装からの参照」と数え、
# 解説文書（SKILL.md 等）の言及で未参照が解消しないようにする。
DOC_SUFFIXES = {".md", ".yaml", ".yml", ".toml", ".txt"}
CODE_SUFFIXES = {".py", ".ts", ".js", ".rs", ".go", ".java"}
# 「テスト/実装からの参照」と見なすワークスペース相対パスの接頭辞（SDD-FR-147）
TRACE_PREFIXES = ("tests", "test", "src", "scripts", "hooks", "skills")
# 検証証跡（SDD-FR-151 / SDD-FR-153）。sdd-test の spec_verify.py が書き、本ツールが検査する
VERIFICATION_DIRNAME = "verification"
# Gate 通過記録（SDD-FR-155）。`.spec/gates/` に置く不変記録で、status 遷移を持たない
GATE_KINDS = {"discovery", "design", "promotion"}
GATE_REQUIRED_KEYS = (
    "id", "gate", "date", "arbiter", "scope", "confirmed_decision_refs", "checklist_ref",
)
EVIDENCE_SCHEMA = "bitzsdd/verification-evidence@1"
EVIDENCE_REQUIRED_KEYS = (
    "command_id", "command", "cwd", "commit", "recorded_at", "exit_code", "requirements",
)


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


def parse_frontmatter_full(text: str) -> dict:
    """parse_frontmatter の拡張版。YAML シーケンス（ブロック / フロー）を list として返す。

    GatePassage の scope / confirmed_decision_refs のように複数値を取る frontmatter を読む。
    スカラーの挙動は parse_frontmatter と同じだが、`#` は**前に空白がある場合だけ**コメントと
    みなす — `checklist_ref` の `path#anchor` を切り落とさないため（SDD-FR-155）。
    """
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    fm = {}
    if not m:
        return fm

    def unquote(val: str) -> str:
        val = val.strip()
        if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
            val = val[1:-1]
        return val

    key = None
    for line in m.group(1).splitlines():
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item is not None and key is not None:
            if not isinstance(fm.get(key), list):
                fm[key] = []
            fm[key].append(unquote(re.sub(r"\s+#.*$", "", item.group(1))))
            continue
        kv = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if kv is None:
            key = None
            continue
        key = kv.group(1)
        val = unquote(re.sub(r"\s+#.*$", "", kv.group(2)))
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = [unquote(part) for part in inner.split(",") if part.strip()]
        else:
            fm[key] = val
    return fm


def load_gate_passages(root: Path):
    """`.spec/gates/*.md` の GatePassage を読む（SDD-FR-155）。

    GatePassage は status 遷移を持たない不変記録であり、ID 書式もライフサイクルも要件と
    異なるため load_requirements のレジストリには混ぜない（spec-issue と同じ扱い）。
    ディレクトリが無いワークスペースでは何も返さず問題も出さない（既存 WS を遡及的に
    FAIL させない）。scope / confirmed_decision_refs の実在検査は check_gate_passages が行う。
    """
    gates, problems = {}, []
    directory = root / ".spec" / "gates"
    if not directory.exists():
        return gates, problems
    for f in sorted(directory.glob("*.md")):
        if f.name.startswith("_"):
            continue
        fm = parse_frontmatter_full(f.read_text(encoding="utf-8"))
        rel = f.relative_to(root)
        gid = fm.get("id")
        if not isinstance(gid, str) or not gid:
            problems.append(f"[gate] {rel}: frontmatter に id がない")
            continue
        if f.stem != gid:
            problems.append(f"[gate] {rel}: ファイル名と id ({gid}) が不一致")
        for required_key in GATE_REQUIRED_KEYS:
            if not fm.get(required_key):
                problems.append(f"[gate] {gid}: {required_key} が未記入")
        kind = fm.get("gate")
        if kind and kind not in GATE_KINDS:
            problems.append(
                f"[gate] {gid}: gate '{kind}' は語彙外（{' / '.join(sorted(GATE_KINDS))}）"
            )
        if gid in gates:
            problems.append(f"[重複] {gid}: IDが重複している")
        gates[gid] = {"fm": fm, "path": f}
    return gates, problems


def gate_field_list(fm: dict, key: str) -> list:
    """frontmatter の複数値フィールドを list に正規化する（単一値のスカラー記法も許す）。"""
    value = fm.get(key)
    if isinstance(value, list):
        return value
    return [value] if value else []


def check_gate_passages(root: Path, gates: dict, global_reqs: dict) -> list:
    """GatePassage の scope と confirmed_decision_refs の実在を検査する（SDD-FR-155）。"""
    problems = []
    resolved_root = root.resolve()
    for gid, gate in sorted(gates.items()):
        for target in gate_field_list(gate["fm"], "scope"):
            if target not in global_reqs:
                problems.append(f"[gate] {gid}: scope の {target} が存在しない（幽霊参照）")
        for ref in gate_field_list(gate["fm"], "confirmed_decision_refs"):
            if ref.startswith("https://"):
                continue
            target = ref.split("#", 1)[0]
            if not target or target.startswith(("/", "~")) or "\\" in target:
                problems.append(
                    f"[gate] {gid}: confirmed_decision_refs はワークスペース相対パスまたは "
                    f"https:// URL を指定する: {ref}"
                )
                continue
            try:
                resolved = (root / target).resolve()
            except OSError:
                resolved = None
            if resolved is None or not resolved.is_relative_to(resolved_root):
                problems.append(
                    f"[gate] {gid}: confirmed_decision_refs がワークスペース外を指している: {ref}"
                )
            elif not resolved.is_file():
                problems.append(
                    f"[gate] {gid}: confirmed_decision_refs の参照先が存在しない: {ref}"
                )
    return problems


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


def impl_code_subdirs(root: Path):
    """実装コードの置き場（コード拡張子だけを走査する追加対象。SDD-FR-147）

    `src` 決め打ちでは拾えない配置を補う。`skills/` 直下は解説文書が主体のため、
    その配下の `scripts/` ディレクトリだけを対象にする。
    """
    subs = [s for s in ("scripts", "hooks") if (root / s).is_dir()]
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        subs += [str(d.relative_to(root))
                 for d in sorted(skills_dir.glob("*/scripts")) if d.is_dir()]
    return subs


def scan_refs(root: Path, subdirs, exclude_names=(), code_only_subdirs=()):
    """subdirs 内の md/コード類から 要件ID → 参照元ファイル一覧 を集める

    code_only_subdirs はコード拡張子のファイルだけを走査する（SDD-FR-147）。
    """
    refs = {}
    for sub in list(subdirs) + list(code_only_subdirs):
        allowed = CODE_SUFFIXES if sub in code_only_subdirs else DOC_SUFFIXES | CODE_SUFFIXES
        d = root / sub
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file() or f.name in exclude_names:
                continue
            if f.suffix not in allowed:
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


def collect_trace_refs(root: Path) -> dict:
    """テスト/実装ディレクトリからの参照だけを集める（ワークスペース横断集約の入力。SDD-FR-146）"""
    return scan_refs(root, ["tests", "test", "src"],
                     exclude_names=("inspection-report.md",),
                     code_only_subdirs=impl_code_subdirs(root))


def build_trace_context(workspaces) -> dict:
    """検査対象の全ワークスペースについて {workspace: {ID: [参照元]}} を作る（SDD-FR-146）"""
    return {w: collect_trace_refs(w) for w in workspaces}


def external_refs_for(root: Path, trace_ctx: dict) -> dict:
    """root 以外のワークスペースが持つ参照を {ID: ["<ワークスペース名>/<相対パス>"]} へ畳む

    単一ワークスペース検査では呼ばれず（trace_ctx が None）、既存の判定を変えない。
    """
    merged = {}
    for w, refs in (trace_ctx or {}).items():
        if w == root:
            continue
        for rid, srcs in refs.items():
            merged.setdefault(rid, []).extend(f"{w.name}/{s}" for s in srcs)
    return merged


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


def git_head_commit(root: Path):
    """ワークスペースの HEAD コミット SHA。git 不在/リポジトリ外は None（縮退）"""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"],
                             cwd=root, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    sha = out.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None


def evidence_is_stale(root: Path, commit: str, cache: dict) -> bool:
    """証跡の commit 以降に、証跡以外のファイルが変更されたか（＝証跡が古いか）。

    HEAD との単純比較は使えない。証跡ファイル自身をコミットすると HEAD が進むため、
    証跡の commit が HEAD と一致することは原理的にありえないため。
    証跡ディレクトリ配下の差分は「ソースの変更」と見なさない。
    """
    if commit in cache:
        return cache[commit]
    stale = True
    try:
        out = subprocess.run(["git", "diff", "--name-only", commit, "HEAD", "--", "."],
                             cwd=root, capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            segment = f".spec/{VERIFICATION_DIRNAME}/"
            stale = any(
                segment not in line.strip()
                for line in out.stdout.splitlines() if line.strip()
            )
    except (OSError, subprocess.SubprocessError):
        stale = True  # 判定できないときは安全側（WARN を出す）
    cache[commit] = stale
    return stale


def load_verification_evidence(root: Path, global_reqs: dict, reqs: dict):
    """`.spec/verification/` の検証証跡を読み、問題・WARN・要件別の索引を返す（SDD-FR-153）。

    証跡ディレクトリが無いワークスペースは従来どおり無検査（加法的導入）。
    存在する証跡が壊れている・失敗している・存在しない要件を指しているのは FAIL。
    証跡が HEAD と違う commit のもの、verified なのに証跡が無い要件は WARN に留める。
    """
    evidence_dir = root / ".spec" / VERIFICATION_DIRNAME
    if not evidence_dir.is_dir():
        return [], [], {}, []

    problems, warnings, by_requirement, records = [], [], {}, []
    head = git_head_commit(root)
    stale_cache: dict = {}
    for path in sorted(evidence_dir.glob("*.json")):
        rel = path.relative_to(root).as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            problems.append(f"[verify] {rel}: 証跡を読み取れません（{error}）")
            continue
        if not isinstance(payload, dict):
            problems.append(f"[verify] {rel}: 証跡の形式が不正です（オブジェクトではない）")
            continue
        if payload.get("schema") != EVIDENCE_SCHEMA:
            problems.append(
                f"[verify] {rel}: schema が {EVIDENCE_SCHEMA} ではありません "
                f"（actual: {payload.get('schema')!r}）")
            continue
        missing = [key for key in EVIDENCE_REQUIRED_KEYS if key not in payload]
        if missing:
            problems.append(f"[verify] {rel}: 必須キーがありません: {', '.join(missing)}")
            continue

        exit_code = payload.get("exit_code")
        if not isinstance(exit_code, int):
            problems.append(f"[verify] {rel}: exit_code が整数ではありません")
        elif exit_code != 0:
            problems.append(f"[verify] {rel}: 失敗した実行の証跡です（exit_code={exit_code}）")

        counts = payload.get("counts")
        if isinstance(counts, dict):
            failed = (counts.get("failed") or 0) + (counts.get("errors") or 0)
            if failed:
                problems.append(f"[verify] {rel}: 失敗・エラーが {failed} 件記録されています")

        requirement_ids = payload.get("requirements")
        if not isinstance(requirement_ids, list) or not requirement_ids:
            problems.append(f"[verify] {rel}: requirements が空です（検証対象が不明）")
            requirement_ids = []
        for rid in requirement_ids:
            if not isinstance(rid, str) or rid not in global_reqs:
                problems.append(f"[verify] {rel}: 参照切れ — 存在しない要件 {rid!r} を指しています")
                continue
            by_requirement.setdefault(rid, []).append(rel)

        commit = payload.get("commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
            problems.append(f"[verify] {rel}: commit が 40 桁の SHA ではありません")
        elif head and commit != head and evidence_is_stale(root, commit, stale_cache):
            warnings.append(
                f"[verify] {rel}: 記録時の commit({commit[:7]}) 以降にソースが変更されています"
                "（再記録が必要な可能性）")
        if payload.get("dirty") is True:
            warnings.append(f"[verify] {rel}: 未コミットの変更がある状態で記録された暫定証跡です")

        records.append((rel, payload))

    for rid, r in sorted(reqs.items()):
        if r["fm"].get("status") not in {"verified", "promoted"}:
            continue
        if r["fm"].get("verification_method") == "manual-check":
            continue
        if rid not in by_requirement:
            warnings.append(f"[verify] {rid}: verified/promoted だが検証証跡がありません")

    return problems, warnings, by_requirement, records


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


def _git(args: list[str], cwd: Path, timeout: int = 10):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout
    )


def audit_baseline_gap(
    root: Path, events_by_artifact: dict[str, list[dict]]
) -> tuple[list[str], list[str]]:
    """Detect human-only transitions that bypassed `spec update` (SDD-FR-143 / SI-SDD-026).

    `.spec/PROJECT.md` が `audit_baseline: <commit-ish>` を宣言した workspace だけで作動する
    opt-in 監査。未宣言なら git を一切呼ばず何も報告しない（通常の inspect 経路を git 必須に
    しないため）。判定は「未記録の到達状態」で行う: baseline 時点の status と、STATE の
    記録済み event の始点（event が無ければ現 status）が食い違い、その到達状態が
    HUMAN_ONLY_STATES なら証跡不在＝規律違反と断定する。

    Returns (problems, warnings). baseline を解決できない環境は FAIL させず WARN に落とす。
    """
    problems: list[str] = []
    warnings: list[str] = []
    project = root / ".spec" / "PROJECT.md"
    if not project.exists():
        return problems, warnings
    baseline = parse_frontmatter(
        project.read_text(encoding="utf-8", errors="replace")
    ).get("audit_baseline", "")
    if not baseline:
        return problems, warnings  # 未宣言 = 従来どおり無検査

    try:
        top = _git(["rev-parse", "--show-toplevel"], root)
        sha = _git(["rev-parse", "--verify", f"{baseline}^{{commit}}"], root)
        if top.returncode or sha.returncode:
            warnings.append(
                f"[audit] WARN: audit_baseline '{baseline}' を解決できず baseline監査を実行できません"
            )
            return problems, warnings
        repo = Path(top.stdout.strip()).resolve()
        baseline_sha = sha.stdout.strip()
        rel = root.resolve().relative_to(repo)
        scope = str(rel / ".spec") if str(rel) != "." else ".spec"
        changed = _git(["diff", "--name-only", baseline_sha, "--", scope], repo)
        if changed.returncode:
            warnings.append(
                f"[audit] WARN: baseline {baseline_sha[:7]} との差分を取得できず baseline監査を実行できません"
            )
            return problems, warnings

        for relpath in changed.stdout.splitlines():
            if not relpath.endswith(".md"):
                continue
            try:
                current_fm = parse_frontmatter(
                    (repo / relpath).read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                continue  # baseline 以降に削除された成果物は監査対象外
            artifact_id = current_fm.get("id", "")
            current_status = current_fm.get("status", "")
            if not artifact_id or not current_status:
                continue
            events = events_by_artifact.get(artifact_id, [])
            # 記録済み遷移より前の「未記録の到達状態」
            reached = events[0]["old"] if events else current_status
            if reached not in HUMAN_ONLY_STATES:
                continue
            shown = _git(["show", f"{baseline_sha}:{relpath}"], repo)
            baseline_status = (
                parse_frontmatter(shown.stdout).get("status", "")
                if shown.returncode == 0
                else ""
            )
            if baseline_status == reached:
                continue  # baseline 時点で既にその状態 = 監査開始前の遷移
            problems.append(
                f"[audit] audit-corruption: {artifact_id} が "
                f"'{baseline_status or '（baseline時点で不在）'}' から '{reached}' へ遷移した記録が "
                f"STATEにありません（baseline {baseline_sha[:7]} 以降。spec update を迂回した手編集の疑い）"
            )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        warnings.append(f"[audit] WARN: baseline監査を実行できません: {exc}")
    return problems, warnings


def check_state_events(root: Path) -> tuple[list[str], list[str]]:
    """Validate structured STATE events and incomplete transactions (SDD-FR-143/145).

    Returns (problems, warnings). warnings は FAIL にしない（decision-ref 参照先消失など）。
    """
    problems = []
    warnings = []
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
        # STATE.md 自体が無い workspace でも baseline 監査は行う
        # （記録の器が無い＝全遷移が未記録であり、監査を素通りさせてはならない）
        baseline_problems, baseline_warnings = audit_baseline_gap(root, {})
        return problems + baseline_problems, warnings + baseline_warnings
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
            schema_version = event.get("schema_version")
            if schema_version not in (1, 2) or not required.issubset(event):
                raise ValueError("schema mismatch")
            if (
                not all(isinstance(event.get(key), str) and event[key]
                        for key in ("event_id", "path", "artifact_id", "old", "new"))
                or not isinstance(event.get("provenance"), dict)
                or not re.fullmatch(r"[0-9a-f]{64}", event.get("artifact_before_hash", ""))
                or not re.fullmatch(r"[0-9a-f]{64}", event.get("artifact_after_hash", ""))
            ):
                raise ValueError("schema type mismatch")
            provenance = event["provenance"]
            kind = provenance.get("kind")
            if not isinstance(kind, str) or not kind:
                raise ValueError("provenance kind missing")
            if kind == "agent-proxy-unverified":
                # SDD-FR-145: 代行遷移は schema v2 と裁定所在参照を必須とする
                if schema_version != 2:
                    raise ValueError("proxy event requires schema_version 2")
                for key in ("actor", "on_behalf_of", "decision_ref"):
                    if not isinstance(provenance.get(key), str) or not provenance[key]:
                        raise ValueError(f"proxy provenance missing {key}")
                ref = provenance["decision_ref"]
                if not ref.startswith("https://"):
                    ref_target = ref.split("#", 1)[0]
                    try:
                        ref_exists = (root / ref_target).exists()
                    except OSError:
                        ref_exists = False
                    if not ref_exists:
                        warnings.append(
                            f"[audit] WARN: {event.get('artifact_id', '?')}の"
                            f"decision-ref参照先が見つかりません: {ref}"
                        )
            elif schema_version != 2:
                pass  # v1 の既存kind（agent / interactive-confirmation-unverified）は従来どおり
            else:
                raise ValueError("schema_version 2 requires proxy provenance")
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

    baseline_problems, baseline_warnings = audit_baseline_gap(root, events_by_artifact)
    problems += baseline_problems
    warnings += baseline_warnings
    return problems, warnings


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


def inspect(root: Path, global_reqs: dict = None, delegation_ctx: tuple = None,
            trace_ctx: dict = None) -> str:
    req_dir = root / ".spec" / "requirements"
    if not req_dir.exists():
        return f"ERROR: {req_dir} が存在しません（BitzSDD レイアウト未初期化）"
    reqs, problems = load_requirements(root)
    if global_reqs is None:
        global_reqs = reqs
    if delegation_ctx is None:
        delegation_ctx = build_delegation_context([root])
    problems += check_delegations(root, *delegation_ctx)
    gates, gate_problems = load_gate_passages(root)
    problems += gate_problems + check_gate_passages(root, gates, global_reqs)
    domains = load_domains(req_dir)
    forbidden = load_forbidden_words(req_dir)
    impl = implements_map(root)
    task_statuses = local_task_statuses(root)
    all_refs = scan_refs(root, [".spec/specs", ".spec/tasks", "tests", "test", "src"],
                         exclude_names=("inspection-report.md",))
    # 実装コードからの参照は未参照判定にだけ使い、幽霊参照判定には入れない（SDD-FR-147 v1.1）。
    # docstring や --help の使用例として書かれた ID を幽霊と誤検知しないため。
    impl_refs = scan_refs(root, [], exclude_names=("inspection-report.md",),
                          code_only_subdirs=impl_code_subdirs(root))
    external_refs = external_refs_for(root, trace_ctx)
    state_problems, state_warnings = check_state_events(root)
    problems += state_problems

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
    # 未参照判定（SDD-FR-146 / SDD-FR-147 / SDD-FR-148）:
    # 自ワークスペースのテスト/実装参照 → 外部ワークスペースの参照 → 検証手段の順に振り分ける
    untested_auto, untested_manual, externally_traced = [], [], {}
    for rid, r in reqs.items():
        if r["fm"].get("status") not in ACTIVE:
            continue
        parts = rid.split("-")
        if (parts[1] if len(parts) > 2 else parts[0]) not in ("FR", "NFR", "CON"):
            continue
        own = all_refs.get(rid, []) + impl_refs.get(rid, [])
        if any(s.startswith(TRACE_PREFIXES) for s in own):
            continue
        ext = external_refs.get(rid, [])
        if ext:
            externally_traced[rid] = ext
            continue
        if r["fm"].get("verification_method") == "manual-check":
            untested_manual.append(rid)
        else:
            untested_auto.append(rid)

    # 検証証跡（SDD-FR-153）。`.spec/verification/` が無ければ従来どおり無検査
    verify_problems, verify_warnings, evidence_by_req, evidence_records = (
        load_verification_evidence(root, global_reqs, reqs)
    )
    problems += verify_problems

    lines = [f"# inspection-report.md ({date.today().isoformat()})", ""]
    lines.append(f"成果物数: {len(reqs)} / 問題: {len(problems)} / 幽霊参照: {len(ghosts)} / 実装待ち: {len(waiting)} / 孤児要件: {len(orphans)} / 検証証跡: {len(evidence_records)}")
    lines.append("")
    lines.append("## 問題一覧")
    lines += [f"- {p}" for p in problems] or ["- なし ✅"]
    lines.append("")
    lines.append("## 幽霊参照（存在しないIDへの参照）")
    lines += [f"- {rid} ← {', '.join(srcs)}" for rid, srcs in sorted(ghosts.items())] or ["- なし ✅"]
    lines.append("")
    lines.append("## 監査 WARN（代行遷移の裁定参照など — FAIL にしない）")
    lines += [f"- {w}" for w in state_warnings] or ["- なし ✅"]
    lines.append("")
    if gates:
        lines.append("## Gate 通過記録（.spec/gates/ — 人間裁定の検分証跡）")
        lines += [
            f"- {gid} — {g['fm'].get('gate', '')} / {g['fm'].get('date', '')} / "
            f"裁定者 {g['fm'].get('arbiter', '')} / 対象 "
            f"{len(gate_field_list(g['fm'], 'scope'))} 件 / 確認した裁定記録 "
            f"{len(gate_field_list(g['fm'], 'confirmed_decision_refs'))} 件"
            for gid, g in sorted(gates.items())
        ]
        lines.append("")
    lines.append("## 実装待ち要件（approved だが implements するタスクがない — WARN）")
    lines += [f"- {rid}" for rid in waiting] or ["- なし ✅"]
    lines.append("")
    lines.append("## 孤児要件（implementing以降なのに implements するタスクがない）")
    lines += [f"- {rid}" for rid in orphans] or ["- なし ✅"]
    lines.append("")
    lines.append("## テスト/実装からの参照がない要件（approved以降）")
    lines += [f"- {rid}" for rid in untested_auto] or ["- なし ✅"]
    lines.append("")
    lines.append("## 参照がない manual-check 要件（テスト参照は原理的に生じない — 検証記録で担保）")
    lines += [f"- {rid}" for rid in untested_manual] or ["- なし ✅"]
    lines.append("")
    lines.append("## 他ワークスペースのテスト/実装から参照されている要件")
    lines += [f"- {rid} ← {', '.join(sorted(srcs))}"
              for rid, srcs in sorted(externally_traced.items())] or ["- なし ✅"]
    lines.append("")
    if evidence_records or verify_warnings:
        lines.append("## 検証証跡（.spec/verification/ — 実出力に基づく機械可読証跡）")
        lines.append("※ 実行時間は observed（非正規）であり一致判定に使わない。判定は exit_code と件数が正")
        lines += [
            f"- {rel} — commit {payload.get('commit', '')[:7]} / "
            f"exit_code {payload.get('exit_code')} / 対象 "
            f"{', '.join(payload.get('requirements') or []) or 'なし'}"
            for rel, payload in evidence_records
        ] or ["- なし"]
        lines.append("")
        lines.append("## 検証証跡の WARN（古い commit・証跡なしの verified 要件 — FAIL にしない）")
        lines += [f"- {w}" for w in verify_warnings] or ["- なし ✅"]
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
                     f"{fm.get('verification_method','')} | {len(impl.get(rid, []))} | "
                     f"{len(all_refs.get(rid, [])) + len(impl_refs.get(rid, []))} |")
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
    # 複数ワークスペース検査のときだけ、テスト/実装参照をグローバルに集約する（SDD-FR-146）。
    # 単一検査では None のままとし、既存の判定と結果を変えない。
    trace_ctx = build_trace_context(workspaces) if len(workspaces) > 1 else None

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
            report = inspect(w, global_reqs, delegation_ctx, trace_ctx)
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
