#!/usr/bin/env python3
"""spec_inspect.py — BitzSDD（bitz-sdd スキル）の構造検証・影響分析ツール（stdlib のみ）

使い方:
  python spec_inspect.py <repo-root>                 # 全検証 → .planning/inspection-report.md
  python spec_inspect.py <repo-root> --impact FR-012 # 変更影響分析（stale候補の列挙）
  python spec_inspect.py <repo-root> --impact-docs docs/02-design/ARCHITECTURE.md
                                                     # docs変更の影響要件（derived_from 逆引き）
"""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ID_RE = re.compile(r"\b(?:FR|NFR|CON)-\d{3}\b")
DOCS_REF_RE = re.compile(r"(docs/[^\s@]+)(?:@([0-9a-fA-F]{7,40}))?")
PREFIXES = ("FR", "NFR", "CON")
STATUSES = {"draft", "approved", "implementing", "verified", "promoted", "deprecated"}
VMETHODS = {"pbt", "example-test", "benchmark", "sast", "dep-audit", "load-test", "manual-check"}
ACTIVE = {"approved", "implementing", "verified", "promoted"}  # 検証対象ステータス


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r"^(\w[\w-]*):\s*(.*?)\s*(?:#.*)?$", line)
            if kv:
                fm[kv.group(1)] = kv.group(2).strip()
    return fm


def load_requirements(req_dir: Path):
    reqs = {}
    problems = []
    for f in sorted(req_dir.glob("*.md")):
        if f.name.startswith("_") or f.name in ("domains.md",):
            continue
        text = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        rid = fm.get("id", "")
        if not rid:
            problems.append(f"[構造] {f.name}: frontmatter に id がない")
            continue
        if f.stem != rid:
            problems.append(f"[構造] {f.name}: ファイル名と id ({rid}) が不一致")
        if not rid.split("-")[0] in PREFIXES:
            problems.append(f"[構造] {rid}: プレフィックスが FR/NFR/CON 以外")
        if rid in reqs:
            problems.append(f"[重複] {rid}: IDが重複している")
        reqs[rid] = {"fm": fm, "text": text, "path": f}
    return reqs, problems


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
    tasks = root / ".planning" / "tasks"
    if not tasks.exists():
        return impl
    for f in tasks.rglob("*.md"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if re.search(r"implements\s*:", line):
                for rid in ID_RE.findall(line):
                    impl.setdefault(rid, []).append(str(f.relative_to(root)))
    return impl


def inspect(root: Path) -> str:
    req_dir = root / ".planning" / "requirements"
    if not req_dir.exists():
        return f"ERROR: {req_dir} が存在しません（BitzSDD レイアウト未初期化）"
    reqs, problems = load_requirements(req_dir)
    domains = load_domains(req_dir)
    forbidden = load_forbidden_words(req_dir)
    impl = implements_map(root)
    all_refs = scan_refs(root, [".planning/specs", ".planning/tasks", "tests", "test", "src"],
                         exclude_names=("inspection-report.md",))

    for rid, r in reqs.items():
        fm = r["fm"]
        st = fm.get("status", "")
        if st not in STATUSES:
            problems.append(f"[frontmatter] {rid}: status '{st}' は語彙外")
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
        for line in body.splitlines():
            if "WHEN" in line and "SHALL" not in line:
                problems.append(f"[lint] {rid}: EARS不完全（WHEN があるのに SHALL がない行）")

    ghosts = {rid: srcs for rid, srcs in all_refs.items() if rid not in reqs}
    orphans = [rid for rid, r in reqs.items()
               if r["fm"].get("status") in ACTIVE and rid not in impl]
    untested = [rid for rid, r in reqs.items()
                if r["fm"].get("status") in ACTIVE
                and not any(s.startswith(("tests", "test", "src")) for s in all_refs.get(rid, []))]

    lines = [f"# inspection-report.md ({date.today().isoformat()})", ""]
    lines.append(f"要件数: {len(reqs)} / 問題: {len(problems)} / 幽霊参照: {len(ghosts)} / 孤児要件: {len(orphans)}")
    lines.append("")
    lines.append("## 問題一覧")
    lines += [f"- {p}" for p in problems] or ["- なし ✅"]
    lines.append("")
    lines.append("## 幽霊参照（存在しないIDへの参照）")
    lines += [f"- {rid} ← {', '.join(srcs)}" for rid, srcs in sorted(ghosts.items())] or ["- なし ✅"]
    lines.append("")
    lines.append("## 孤児要件（approved以降なのに implements するタスクがない）")
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
        lines.append(f"| {rid} | {fm.get('status','')} | {fm.get('domain','')} | "
                     f"{fm.get('verification_method','')} | {len(impl.get(rid, []))} | {len(all_refs.get(rid, []))} |")
    ok = not problems and not ghosts and not orphans
    lines.append("")
    lines.append("**判定: " + ("PASS ✅" if ok else "FAIL ❌（上記を解消するまで verified に進めない）") + "**")
    return "\n".join(lines)


def impact(root: Path, target: str) -> str:
    req_dir = root / ".planning" / "requirements"
    reqs, _ = load_requirements(req_dir)
    if target not in reqs:
        return f"ERROR: {target} は登録簿に存在しません"
    ver = reqs[target]["fm"].get("version", "?")
    all_refs = scan_refs(root, [".planning/specs", ".planning/tasks", "tests", "test", "src", "docs"],
                         exclude_names=("inspection-report.md",))
    hits = sorted(set(all_refs.get(target, [])))
    lines = [f"# impact: {target}@{ver}", "",
             f"依存成果物: {len(hits)} 件。各成果物に `stale: {target}@{ver}` を付与し、更新済みから外すこと。", ""]
    lines += [f"- [ ] {h}" for h in hits] or ["- 依存成果物なし"]
    supers = [rid for rid, r in reqs.items() if r["fm"].get("supersedes") == target]
    if supers:
        lines.append(f"\n後継要件: {', '.join(supers)}")
    return "\n".join(lines)


def impact_docs(root: Path, target: str) -> str:
    """docs/ 文書の変更が影響する要件を derived_from の逆引きで列挙する（再伝播プロトコルの候補列挙）"""
    req_dir = root / ".planning" / "requirements"
    if not req_dir.exists():
        return f"ERROR: {req_dir} が存在しません（BitzSDD レイアウト未初期化）"
    reqs, _ = load_requirements(req_dir)
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
        rows.append(f"- [ ] {rid} (status: {r['fm'].get('status', '')}) — {state}")
    lines = [f"# impact-docs: {target}", ""]
    if current:
        lines.append(f"現行コミット: {current[:12]}")
    lines.append(f"派生要件: {len(rows)} 件。乖離のあるものは references/lifecycle.md の"
                 "再伝播プロトコル（判定パス→人間確認→最小再実行）に従い stale を付与すること。")
    lines.append("")
    lines += rows or ["- この文書から派生した要件はありません"]
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    root = Path(sys.argv[1]).resolve()
    if "--impact-docs" in sys.argv:
        target = sys.argv[sys.argv.index("--impact-docs") + 1]
        print(impact_docs(root, target))
    elif "--impact" in sys.argv:
        target = sys.argv[sys.argv.index("--impact") + 1]
        print(impact(root, target))
    else:
        report = inspect(root)
        out = root / ".planning" / "inspection-report.md"
        if not report.startswith("ERROR"):
            out.write_text(report + "\n", encoding="utf-8")
            print(report)
            print(f"\n→ {out} に保存しました")
        else:
            print(report)
            sys.exit(1)


if __name__ == "__main__":
    main()
