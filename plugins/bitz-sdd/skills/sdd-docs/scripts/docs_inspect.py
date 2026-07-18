#!/usr/bin/env python3
"""
docs_inspect.py — docs/ 側（人間ナラティブ層）の構造検証。

spec_inspect.py（.spec/ 側）と対になる。stdlib のみ。
検査対象:
  - frontmatter 必須項目・enum・id 形式・semver・日付
  - 日本語6章、宣言式の任意章・管理対象外、章と機械 area の対応
  - status: superseded のとき superseded_by 必須、かつ実在 DOC-id を指すこと
  - MASTER.md レジストリ ⇔ 実ファイルの照合（ghost / orphan）
  - project_type 整合（MASTER が library/both のとき 公開API.md 必須 ほか）
  - （任意）requirements の decided_by ADR ⇔ 意思決定/ADR-*.md のブリッジ

使い方:
  python docs_inspect.py <repo-root>            # → docs-inspection-report.md
  python docs_inspect.py <repo-root> --json     # 機械可読出力
  python docs_inspect.py <repo-root> --strict   # WARN も非ゼロ終了に含める

既存 spec_inspect.py へ取り込む場合:
  from docs_inspect import run_docs_checks
  findings += run_docs_checks(repo_root)      # Finding は (severity, code, path, message)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass

# ---- 定数（_conventions.md / _scaling.md と一致させること） -------------------

STATUS_ENUM = {"proposed", "active", "deprecated", "superseded"}
IMPACT_ENUM = {"low", "medium", "high"}
PTYPE_ENUM = {"app", "library", "both"}
REQUIRED_FM = ["id", "title", "status", "version", "changeImpact",
               "project_type", "updated", "owner"]

# 日本語の章と、既存 DOC-id で維持する英語 area の許容集合。
# 章と area は意図的に多対多であり、SDD-DSN-002 の表と一致させること。
FOLDER_AREAS = {
    "00_はじめに": {"context", "governance"},
    "01_システム仕様": {"system"},
    "02_ユースケース": {"usecase"},
    "03_設計仕様": {"design", "implementation"},
    "04_テスト仕様": {"quality"},
    "05_リリース・運用": {"operations", "knowledge"},
    "06_リファレンス": {"reference"},
}
MANDATORY_FOLDERS = tuple(list(FOLDER_AREAS)[:6])
OPTIONAL_FOLDERS = {"reference": "06_リファレンス"}
LEGACY_FOLDERS = {
    "01-context", "02-design", "03-implementation", "04-quality",
    "05-operations", "06-reference", "07-governance", "08-knowledge",
}
VALID_AREAS = set().union(*FOLDER_AREAS.values())

ID_RE = re.compile(r"^DOC-(?:master|[a-z0-9]+(?:-[a-z0-9]+)*)$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DOCID_IN_CELL = re.compile(r"DOC-[a-z0-9-]+")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
DECIDED_BY = re.compile(r"decided_by:\s*['\"]?(ADR-\d+)")

# frontmatter を持たない/検査対象外のファイル
EXEMPT_BASENAMES = {"README.md"}
EXEMPT_PREFIX = "_"           # _conventions.md, _scaling.md
TEMPLATE_SUFFIX = "-template.md"  # ADR-template.md, POSTMORTEM-template.md


@dataclass
class Finding:
    severity: str   # ERROR | WARN | INFO
    code: str
    path: str
    message: str


# ---- 最小 frontmatter パーサ（pyyaml 非依存） --------------------------------

def parse_frontmatter(text: str):
    """先頭 --- ... --- の flat な key: value を dict で返す。無ければ None。"""
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fm = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("#"):
            val = None
        elif val and val[0] in "\"'":
            # クォート文字列: 閉じクォートまでを値とし、以降（コメント）は捨てる
            q = val[0]
            end = val.find(q, 1)
            val = val[1:end] if end != -1 else val[1:]
        else:
            # 非クォート: 空白+# 以降を YAML インラインコメントとして除去
            val = re.split(r"\s+#", val, 1)[0].strip()
        if val in ("null", "~", ""):
            val = None
        fm[key] = val
    return None  # 終端 --- が無い


# ---- 走査 -------------------------------------------------------------------

def resolve_docs_dir(root: str) -> str | None:
    if os.path.isdir(os.path.join(root, "docs")):
        return os.path.join(root, "docs")
    if os.path.basename(os.path.normpath(root)) == "docs" and os.path.isdir(root):
        return root
    return None


def is_exempt(basename: str) -> bool:
    return (basename in EXEMPT_BASENAMES
            or basename.startswith(EXEMPT_PREFIX)
            or basename.endswith(TEMPLATE_SUFFIX))


def folder_key(rel_path: str) -> str | None:
    """rel_path の先頭ディレクトリが正規章なら返す。"""
    parts = rel_path.replace("\\", "/").split("/")
    return parts[0] if parts and parts[0] in FOLDER_AREAS else None


def parse_csv(value) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def is_under(rel_path: str, parents) -> bool:
    rel = rel_path.replace("\\", "/").strip("/")
    return any(rel == parent or rel.startswith(parent + "/") for parent in parents)


def collect_docs(docs_dir: str, excluded_paths=()):
    """[(rel_path, abs_path, frontmatter_or_None, exempt_bool)] を返す。"""
    out = []
    for dirpath, dirs, files in os.walk(docs_dir):
        rel_dir = os.path.relpath(dirpath, docs_dir)
        rel_dir = "" if rel_dir == "." else rel_dir.replace("\\", "/")
        dirs[:] = [
            name for name in dirs
            if not is_under("/".join(filter(None, (rel_dir, name))), excluded_paths)
        ]
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            ab = os.path.join(dirpath, f)
            rel = os.path.relpath(ab, docs_dir)
            try:
                text = open(ab, encoding="utf-8").read()
            except Exception:
                text = ""
            fm = parse_frontmatter(text)
            out.append((rel, ab, fm, is_exempt(f)))
    return out


# ---- 各チェック --------------------------------------------------------------

def check_frontmatter(rel, fm, docid_area):
    fs = []
    for key in REQUIRED_FM:
        if key not in fm or fm[key] is None:
            fs.append(Finding("ERROR", "FM_MISSING", rel, f"必須frontmatter '{key}' が無い"))
    st = fm.get("status")
    if st is not None and st not in STATUS_ENUM:
        fs.append(Finding("ERROR", "FM_ENUM", rel, f"status '{st}' は不正 (許容: {sorted(STATUS_ENUM)})"))
    ci = fm.get("changeImpact")
    if ci is not None and ci not in IMPACT_ENUM:
        fs.append(Finding("ERROR", "FM_ENUM", rel, f"changeImpact '{ci}' は不正"))
    pt = fm.get("project_type")
    if pt is not None and pt not in PTYPE_ENUM:
        fs.append(Finding("ERROR", "FM_ENUM", rel, f"project_type '{pt}' は不正"))
    ver = fm.get("version")
    if ver is not None and not SEMVER_RE.match(str(ver)):
        fs.append(Finding("ERROR", "FM_SEMVER", rel, f"version '{ver}' は semver でない"))
    upd = fm.get("updated")
    if upd is not None and not DATE_RE.match(str(upd)):
        fs.append(Finding("WARN", "FM_DATE", rel, f"updated '{upd}' は ISO 日付 (YYYY-MM-DD) でない"))
    did = fm.get("id")
    if did is not None and not ID_RE.match(str(did)):
        fs.append(Finding("ERROR", "ID_FORMAT", rel, f"id '{did}' は DOC-<area>-<slug> 形式でない"))
    # id の area 部と実フォルダの許容集合との一致
    fk = folder_key(rel)
    if did and fk and did != "DOC-master":
        m = re.match(r"^DOC-([a-z0-9]+)-", str(did))
        area = m.group(1) if m else None
        if area and area in VALID_AREAS and area not in FOLDER_AREAS[fk]:
            fs.append(Finding("ERROR", "AREA_MISMATCH", rel,
                              f"id area '{area}' が章 {fk}(許容: {sorted(FOLDER_AREAS[fk])}) と不一致"))
    return fs


def check_layout(docs_dir, master_fm):
    fs = []
    declared = set(parse_csv((master_fm or {}).get("optional_chapters")))
    unknown = declared - set(OPTIONAL_FOLDERS)
    for name in sorted(unknown):
        fs.append(Finding("ERROR", "OPTIONAL_UNKNOWN", "MASTER.md",
                          f"optional_chapters '{name}' は未対応"))

    for folder in MANDATORY_FOLDERS:
        if not os.path.isdir(os.path.join(docs_dir, folder)):
            fs.append(Finding("ERROR", "LAYOUT_MISSING", folder,
                              "必須章が存在しない"))
    for folder in sorted(LEGACY_FOLDERS):
        if os.path.isdir(os.path.join(docs_dir, folder)):
            fs.append(Finding("ERROR", "LAYOUT_LEGACY", folder,
                              "旧英語8章が日本語6章と混在している"))

    for name, folder in OPTIONAL_FOLDERS.items():
        exists = os.path.isdir(os.path.join(docs_dir, folder))
        if exists and name not in declared:
            fs.append(Finding("ERROR", "OPTIONAL_UNDECLARED", folder,
                              f"MASTER.md に optional_chapters: {name} の宣言がない"))
        if name in declared and not exists:
            fs.append(Finding("ERROR", "OPTIONAL_MISSING", folder,
                              f"optional_chapters: {name} を宣言したが章が存在しない"))

    allowed = set(MANDATORY_FOLDERS) | {
        folder for name, folder in OPTIONAL_FOLDERS.items() if name in declared
    }
    for name in sorted(os.listdir(docs_dir)):
        if re.match(r"^\d{2}[-_]", name) and name not in allowed and name not in LEGACY_FOLDERS:
            fs.append(Finding("ERROR", "LAYOUT_UNKNOWN", name,
                              "未定義の番号章。必須6章または宣言済み任意章だけを使用する"))
    return fs


def validate_excluded_paths(master_fm):
    valid = []
    fs = []
    protected = set(MANDATORY_FOLDERS) | set(OPTIONAL_FOLDERS.values())
    for raw in parse_csv((master_fm or {}).get("excluded_paths")):
        normalized = os.path.normpath(raw).replace("\\", "/")
        first = normalized.split("/", 1)[0]
        invalid = (
            os.path.isabs(raw)
            or normalized in (".", "..")
            or normalized.startswith("../")
            or first in protected
            or first in {"MASTER.md", "_conventions.md", "_scaling.md"}
        )
        if invalid:
            fs.append(Finding("ERROR", "EXCLUDED_INVALID", "MASTER.md",
                              f"excluded_paths '{raw}' は管理章またはdocs外を隠し得る"))
        else:
            valid.append(normalized.strip("/"))
    return valid, fs


def check_supersede(all_by_id):
    fs = []
    ids = set(all_by_id)
    for did, (rel, fm) in all_by_id.items():
        if fm.get("status") == "superseded":
            sb = fm.get("superseded_by")
            if not sb:
                fs.append(Finding("ERROR", "SUPERSEDE_MISSING", rel,
                                  "status=superseded だが superseded_by が無い"))
            elif sb not in ids:
                fs.append(Finding("ERROR", "SUPERSEDE_DANGLING", rel,
                                  f"superseded_by '{sb}' が実在しない DOC-id"))
    return fs


def parse_master_registry(docs_dir):
    """MASTER.md のテーブル行から (id, linked_path) を集める。"""
    master = os.path.join(docs_dir, "MASTER.md")
    entries = []
    master_fm = None
    if not os.path.isfile(master):
        return entries, master_fm
    text = open(master, encoding="utf-8").read()
    master_fm = parse_frontmatter(text) or {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        idm = DOCID_IN_CELL.search(line)
        linkm = MD_LINK.search(line)
        if idm and linkm:
            entries.append((idm.group(0), linkm.group(1).strip()))
    return entries, master_fm


def check_registry(docs_dir, docs, registry, excluded_paths=()):
    fs = []
    reg_paths = {}
    for rid, rpath in registry:
        norm = os.path.normpath(rpath)
        reg_paths[norm] = rid
        if is_under(norm, excluded_paths):
            fs.append(Finding("ERROR", "REG_EXCLUDED", "MASTER.md",
                              f"レジストリ行 {rid} が管理対象外パス {rpath} を指している"))
        if not os.path.isfile(os.path.join(docs_dir, rpath)):
            fs.append(Finding("ERROR", "REG_GHOST", "MASTER.md",
                              f"レジストリ行 {rid} → {rpath} の実ファイルが無い"))
    # orphan: 実ファイルなのにレジストリ未登録（exempt/テンプレ/ADR実体/decisions以下は除外）
    listed = {os.path.normpath(p) for _, p in registry}
    for rel, _ab, fm, exempt in docs:
        if exempt:
            continue
        base = os.path.basename(rel)
        if base == "MASTER.md":   # レジストリ本体は自身に載らない
            continue
        # ADR 実体・postmortem 実体は別表/別管理のため orphan 対象外
        normalized_rel = "/" + rel.replace("\\", "/")
        if "/意思決定/" in normalized_rel or "/ポストモーテム/" in normalized_rel:
            continue
        if os.path.normpath(rel) not in listed:
            fs.append(Finding("WARN", "REG_ORPHAN", rel,
                              "実在するが MASTER.md レジストリに未登録"))
    return fs


def check_project_type(docs_dir, docs, master_fm):
    fs = []
    proj = (master_fm or {}).get("project_type")
    if proj is None:
        fs.append(Finding("WARN", "PT_MASTER_MISSING", "MASTER.md",
                          "MASTER.md に project_type 宣言が無い"))
        return fs
    if proj not in PTYPE_ENUM:
        return fs  # 形式エラーは check_frontmatter 側で拾う
    has_public_api = os.path.isfile(os.path.join(docs_dir, "03_設計仕様", "公開API.md"))
    if proj in ("library", "both") and not has_public_api:
        fs.append(Finding("ERROR", "PT_NO_PUBLIC_API", "03_設計仕様/",
                          f"project_type={proj} だが 公開API.md が無い（library は必須）"))
    if proj == "app" and has_public_api:
        fs.append(Finding("WARN", "PT_APP_HAS_PUBLIC_API", "03_設計仕様/公開API.md",
                          "project_type=app に library 専用の 公開API.md がある"))
    # 各文書の project_type が MASTER(app/library) と矛盾していないか
    if proj in ("app", "library"):
        for rel, _ab, fm, exempt in docs:
            if exempt or not fm:
                continue
            pt = fm.get("project_type")
            if pt in ("app", "library") and pt != proj:
                fs.append(Finding("WARN", "PT_DOC_CONFLICT", rel,
                                  f"文書 project_type='{pt}' が MASTER='{proj}' と矛盾"))
    return fs


def check_adr_bridge(root, docs_dir):
    """任意: .spec/requirements/ 内の md ファイルの decided_by ADR が decisions/ に存在するか。"""
    fs = []
    req_dir = os.path.join(root, ".spec", "requirements")
    if not os.path.isdir(req_dir):
        return fs
    referenced = set()
    for f in os.listdir(req_dir):
        if not f.endswith(".md") or f.startswith("_"):
            continue
        try:
            text = open(os.path.join(req_dir, f), encoding="utf-8").read()
            for adr in DECIDED_BY.findall(text):
                referenced.add(adr)
        except Exception:
            continue
    dec_dir = os.path.join(docs_dir, "03_設計仕様", "意思決定")
    present = set()
    if os.path.isdir(dec_dir):
        for f in os.listdir(dec_dir):
            m = re.match(r"^(ADR-\d+)", f)
            if m:
                present.add(m.group(1))
    for adr in sorted(referenced - present):
        fs.append(Finding("WARN", "ADR_BRIDGE", ".spec/requirements/",
                          f"decided_by {adr} に対応する docs/03_設計仕様/意思決定/{adr}-*.md が無い"))
    return fs


# ---- ランナー ---------------------------------------------------------------

def run_docs_checks(root: str):
    docs_dir = resolve_docs_dir(root)
    if not docs_dir:
        return [Finding("ERROR", "NO_DOCS", root, "docs/ ディレクトリが見つからない")]

    findings: list[Finding] = []
    all_by_id: dict[str, tuple] = {}

    registry, master_fm = parse_master_registry(docs_dir)
    excluded_paths, excluded_findings = validate_excluded_paths(master_fm)
    findings += excluded_findings
    findings += check_layout(docs_dir, master_fm)
    docs = collect_docs(docs_dir, excluded_paths)

    for rel, _ab, fm, exempt in docs:
        if exempt:
            continue
        if fm is None:
            findings.append(Finding("ERROR", "FM_ABSENT", rel, "frontmatter が無い"))
            continue
        findings += check_frontmatter(rel, fm, None)
        did = fm.get("id")
        if did:
            if did in all_by_id:
                findings.append(Finding("ERROR", "ID_DUP", rel,
                                        f"id '{did}' が重複 (既出: {all_by_id[did][0]})"))
            else:
                all_by_id[did] = (rel, fm)

    findings += check_supersede(all_by_id)
    findings += check_registry(docs_dir, docs, registry, excluded_paths)
    findings += check_project_type(docs_dir, docs, master_fm)
    findings += check_adr_bridge(root, docs_dir)
    return findings


# ---- 出力 -------------------------------------------------------------------

SEV_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}


def render_report(findings) -> str:
    n_err = sum(1 for f in findings if f.severity == "ERROR")
    n_warn = sum(1 for f in findings if f.severity == "WARN")
    n_info = sum(1 for f in findings if f.severity == "INFO")
    lines = ["# docs/ Inspection Report", "",
             f"- ERROR: {n_err} / WARN: {n_warn} / INFO: {n_info}", ""]
    if not findings:
        lines.append("問題は検出されませんでした。")
        return "\n".join(lines) + "\n"
    for sev in ("ERROR", "WARN", "INFO"):
        group = [f for f in findings if f.severity == sev]
        if not group:
            continue
        lines.append(f"## {sev} ({len(group)})")
        lines.append("")
        lines.append("| code | path | message |")
        lines.append("|---|---|---|")
        for f in sorted(group, key=lambda x: (x.code, x.path)):
            msg = f.message.replace("|", "\\|")
            lines.append(f"| {f.code} | `{f.path}` | {msg} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="docs/ 側の構造検証")
    ap.add_argument("root", help="リポジトリルート（または docs/ 直下）")
    ap.add_argument("--json", action="store_true", help="JSON 出力")
    ap.add_argument("--strict", action="store_true", help="WARN も失敗扱い")
    ap.add_argument("-o", "--out", default="docs-inspection-report.md")
    args = ap.parse_args(argv)

    findings = run_docs_checks(args.root)

    if args.json:
        import json
        print(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2))
    else:
        report = render_report(findings)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
        sys.stdout.write(report)
        sys.stderr.write(f"\n→ {args.out} に書き出しました\n")

    n_err = sum(1 for f in findings if f.severity == "ERROR")
    n_warn = sum(1 for f in findings if f.severity == "WARN")
    fail = n_err + (n_warn if args.strict else 0)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
