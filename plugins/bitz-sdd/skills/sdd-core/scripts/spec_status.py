#!/usr/bin/env python3
"""spec_status.py — BitzSDD（sdd-core スキル）の軽量状況照会ツール（stdlib のみ・読み取り専用）

「いま何フェーズか・要件/spec-issue/タスクが何件どの status か・次に何をすべきか」を
.spec/ を読み歩く代わりに1コマンドで得るための照会ツール。**.spec/ へは一切書き込まない**。

sdd_report.py との棲み分け:
  - sdd_report.py  … 人間向けの詳細レポートを .spec/reports/ に生成する（ファイル出力あり）
  - spec_status.py … 軽量な即時照会。標準出力にテキスト or JSON を出すだけ（ファイル出力なし）

使い方:
  python spec_status.py <repo-root>                 # 人間向けテキストサマリ
  python spec_status.py <repo-root> --json          # エージェント向け JSON
  python spec_status.py --workspace . plugins/*     # 複数ワークスペースを一括照会
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_labels import phase_label, status_label  # noqa: E402

# 要件が「承認済み以降（検証対象）」とみなされる status
APPROVED_PLUS = {"approved", "implementing", "verified", "promoted"}
# 要件が「検証済み」とみなされる status
VERIFIED = {"verified", "promoted"}
# タスクが「完了」とみなされる status
TASK_DONE = {"done", "complete", "completed", "verified", "promoted"}

# requirements/ で要件ファイルとして数えない補助ファイル
NON_REQUIREMENT_FILES = {"domains.md"}

# determine_phase() が返しうるフェーズ語彙の正（SDD-FR-136）。
# phase_code は JSON 出力の公開契約 — 既存値の削除・改名は後方互換違反（変更は加算のみ）。
# SKILL.md のフェーズ・ルーティング表と references/gates.md はこの7語に従う。
PHASE_CODES = ("map", "discovery", "design", "plan", "execute", "verify", "done")


def parse_frontmatter(text: str) -> dict:
    """spec_inspect.py と同一挙動の軽量 frontmatter パーサ。"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r"^(\w[\w-]*):\s*(.*?)\s*(?:#.*)?$", line)
            if kv:
                val = kv.group(2).strip()
                if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                    val = val[1:-1]
                fm[kv.group(1)] = val
    return fm


def _statuses_in(directory: Path, *, skip=frozenset()) -> Counter:
    """ディレクトリ直下の *.md の frontmatter status を集計する（読み取り専用）。"""
    counter = Counter()
    if not directory.exists():
        return counter
    for f in sorted(directory.glob("*.md")):
        if f.name.startswith("_") or f.name in skip:
            continue
        fm = parse_frontmatter(f.read_text(encoding="utf-8"))
        counter[fm.get("status") or "(none)"] += 1
    return counter


IMPLEMENTED_MARKER_RE = re.compile(r"^\s*-\s*\*\*実施\*\*:", re.M)


def _accepted_issue_records(directory: Path) -> list:
    """status: accepted の spec-issue の構造化レコードを返す（読み取り専用）。

    各レコードは {"id", "has_marker", "delegated"}:
      - has_marker: 本文に `**実施**:` マーカー（軽量レーンでの直接反映済み）を持つ
      - delegated:  frontmatter に `delegated_to:` を持つ（クロス WS 委譲済み。SDD-FR-141）
    accepted 分類（対応済み / 委譲済み・未解決 / 未着手）と実施記録欠落検出（SDD-FR-142）は
    呼び出し側の collect() が origin 参照と突き合わせて判定する。
    """
    records = []
    if not directory.exists():
        return records
    for f in sorted(directory.glob("*.md")):
        if f.name.startswith("_"):
            continue
        text = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm.get("status") != "accepted":
            continue
        records.append({
            "id": fm.get("id") or f.stem,
            "has_marker": bool(IMPLEMENTED_MARKER_RE.search(text)),
            "delegated": bool(fm.get("delegated_to")),
        })
    return records


def _origin_records(directory: Path) -> list:
    """requirements/*.md の (origin テキスト, 要件 status) ペアを集める（読み取り専用）。

    origin テキストは accepted spec-issue の対応済み判定（部分一致）に、status は
    実施記録欠落警告（参照元要件が verified/promoted か。SDD-FR-142）に使う。
    """
    records = []
    if not directory.exists():
        return records
    for f in sorted(directory.glob("*.md")):
        if f.name.startswith("_") or f.name in NON_REQUIREMENT_FILES:
            continue
        fm = parse_frontmatter(f.read_text(encoding="utf-8"))
        origin = fm.get("origin")
        if origin:
            records.append((origin, fm.get("status") or "(none)"))
    return records


def determine_phase(reqs: Counter, tasks: Counter, has_discovery: bool,
                    has_design: bool = False):
    """成果物の有無から現在フェーズを機械的に推定する。

    Returns: (phase_code, phase_label) — phase_code は PHASE_CODES の7語のいずれか。
    要件が1件でもあれば設計成果物の有無にかかわらず plan 以降の判定を適用する
    （要件の起票をもって Plan フェーズ入りとみなす。SDD-FR-136）。
    """
    n_reqs = sum(reqs.values())
    n_appr = sum(v for s, v in reqs.items() if s in APPROVED_PLUS)
    n_ver = sum(v for s, v in reqs.items() if s in VERIFIED)
    n_tasks = sum(tasks.values())
    n_done = sum(v for s, v in tasks.items() if s in TASK_DONE)

    if n_reqs == 0 and n_tasks == 0:
        if has_design:
            code = "design"
        elif has_discovery:
            code = "discovery"
        else:
            code = "map"
    elif n_appr == 0 or n_tasks == 0:
        # 要件未承認・タスク未分解のいずれも Plan。どちらであるかは next_actions が示す
        code = "plan"
    elif n_done < n_tasks:
        code = "execute"
    elif n_ver < n_appr:
        code = "verify"
    else:
        code = "done"
    return (code, phase_label(code))


def next_actions(reqs: Counter, issues: Counter, tasks: Counter, phase_code: str,
                  accepted_unaddressed=(), accepted_delegated_unresolved=(),
                  completion_record_missing=()):
    """状況から次アクション候補を単純ヒューリスティックで導く。"""
    actions = []
    n_open = issues.get("open", 0)
    n_draft = reqs.get("draft", 0)
    n_appr = sum(v for s, v in reqs.items() if s in APPROVED_PLUS)
    n_ver = sum(v for s, v in reqs.items() if s in VERIFIED)
    n_tasks = sum(tasks.values())
    n_done = sum(v for s, v in tasks.items() if s in TASK_DONE)
    n_pending_tasks = n_tasks - n_done

    if n_open:
        actions.append(f"未裁定の spec-issue が {n_open} 件 — 人間裁定（accept/reject）を行う")
    if accepted_unaddressed:
        ids = "、".join(accepted_unaddressed)
        actions.append(
            f"accepted のまま未着手の spec-issue が {len(accepted_unaddressed)} 件"
            f"（{ids}） — 要件化 or 軽量レーンでの実施を検討する"
        )
    if accepted_delegated_unresolved:
        ids = "、".join(accepted_delegated_unresolved)
        actions.append(
            f"委譲済み（delegated_to）で未解決の accepted spec-issue が "
            f"{len(accepted_delegated_unresolved)} 件（{ids}） — 委譲先 workspace を含む "
            f"`--workspace` 一括実行で判定するか、委譲先の要件化状況を確認する"
        )
    if completion_record_missing:
        ids = "、".join(completion_record_missing)
        actions.append(
            f"実施記録（`- **実施**:`）の欠落が {len(completion_record_missing)} 件"
            f"（{ids}） — 対象 spec-issue に参照要件 ID・PR 等を添えた実施マーカーを追記する"
        )
    if n_draft:
        actions.append(f"draft 要件が {n_draft} 件 — 承認（approved 化）を行う")
    if phase_code == "design":
        actions.append("設計成果物あり — sdd-review の実施と統合判定の取得で Design Gate 通過を準備する")
    if phase_code == "plan" and n_appr and n_tasks == 0:
        actions.append("承認済み要件を sdd-implement でタスクへ分解する")
    if n_pending_tasks > 0:
        actions.append(f"未完了タスクが {n_pending_tasks} 件 — 実装を進める")
    if phase_code == "verify" or (n_appr and n_ver < n_appr and n_pending_tasks == 0):
        actions.append("sdd-test で検証し要件を verified に昇格する")
    if not actions:
        actions.append("未処理の作業なし（クリーン）")
    return actions


def collect(root: Path, all_origin_records=()) -> dict:
    """1ワークスペースの状況を集計して dict を返す（読み取り専用）。

    all_origin_records: 同一起動で対象になっている全 workspace（自身を含む）の
    requirements の (origin テキスト, 要件 status) ペア一覧。accepted spec-issue の
    対応済み判定・委譲済み分離（SDD-FR-141）・実施記録欠落検出（SDD-FR-142）に使う
    （CORE-FR-012 — workspace 間の委託を許容するため単一 workspace には閉じない）。
    """
    spec = root / ".spec"
    reqs = _statuses_in(spec / "requirements", skip=NON_REQUIREMENT_FILES)
    issues = _statuses_in(spec / "spec-issues")
    tasks = _statuses_in(spec / "tasks")
    has_discovery = (spec / "discovery").exists() and any((spec / "discovery").glob("*.md"))
    # design は stories/ 等のサブディレクトリ成果物も設計中とみなすため再帰で検出する（SDD-FR-136）
    has_design = (spec / "design").exists() and any((spec / "design").rglob("*.md"))

    # accepted spec-issue を3分類する（SDD-FR-141）:
    #   ①対応済み（実施マーカー or スコープ内 origin 参照）→ どのリストにも入れない
    #   ②委譲済み・未解決（delegated_to あり かつ ①非該当）→ accepted_delegated_unresolved
    #   ③未着手（それ以外）→ accepted_unaddressed（従来どおり）
    # あわせて、①のうち origin 参照元要件が verified/promoted かつ実施マーカー欠落のものを
    # completion_record_missing に計上する（SDD-FR-142。記録の督促。判定・件数は①に影響しない）。
    accepted_unaddressed = []
    accepted_delegated_unresolved = []
    completion_record_missing = []
    for rec in _accepted_issue_records(spec / "spec-issues"):
        iid = rec["id"]
        matching_statuses = [st for (text, st) in all_origin_records if iid in text]
        if rec["has_marker"]:
            continue  # 実施マーカーで対応済み。記録も揃っており警告不要
        if matching_statuses:
            # origin 参照で対応済みだが実施マーカーが無い。参照元が verified/promoted なら記録欠落
            if any(st in VERIFIED for st in matching_statuses):
                completion_record_missing.append(iid)
            continue
        if rec["delegated"]:
            accepted_delegated_unresolved.append(iid)
        else:
            accepted_unaddressed.append(iid)

    phase_code, phase_label = determine_phase(reqs, tasks, has_discovery, has_design)
    return {
        "root": str(root),
        "phase": phase_label,
        "phase_code": phase_code,
        "requirements": {"total": sum(reqs.values()), "by_status": dict(reqs)},
        "spec_issues": {"total": sum(issues.values()), "by_status": dict(issues)},
        "tasks": {"total": sum(tasks.values()), "by_status": dict(tasks)},
        "accepted_unaddressed": accepted_unaddressed,
        "accepted_delegated_unresolved": accepted_delegated_unresolved,
        "completion_record_missing": completion_record_missing,
        "next_actions": next_actions(
            reqs, issues, tasks, phase_code, accepted_unaddressed,
            accepted_delegated_unresolved, completion_record_missing,
        ),
    }


def _fmt_counts(section: dict, kind: str) -> str:
    if not section["by_status"]:
        return "  （0 件）"
    return "\n".join(f"  - {status_label(kind, status)}: {n}"
                     for status, n in sorted(section["by_status"].items()))


def render_text(results) -> str:
    out = []
    for ws in results:
        out.append(f"# ワークスペース: {ws['root']}")
        out.append(f"- フェーズ: {ws['phase']}")
        out.append(f"## 要件 (requirements) — 合計 {ws['requirements']['total']}")
        out.append(_fmt_counts(ws["requirements"], "requirement"))
        out.append(f"## spec-issue — 合計 {ws['spec_issues']['total']}")
        out.append(_fmt_counts(ws["spec_issues"], "spec-issue"))
        out.append(f"## タスク (tasks) — 合計 {ws['tasks']['total']}")
        out.append(_fmt_counts(ws["tasks"], "task"))
        out.append("## 次アクション候補")
        out.extend(f"  - {a}" for a in ws["next_actions"])
        out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="BitzSDD 軽量状況照会ツール（読み取り専用）")
    parser.add_argument("roots", nargs="*", default=["."], help="Workspace roots")
    parser.add_argument("--workspace", nargs="+",
                        help="Explicitly specify workspace roots (overrides positional roots)")
    parser.add_argument("--json", action="store_true", help="機械可読な JSON を出力する")
    args = parser.parse_args()

    candidates = [Path(p).resolve() for p in (args.workspace if args.workspace else args.roots)]
    workspaces = [w for w in candidates if w.is_dir() and (w / ".spec").exists()]

    if not workspaces:
        print("ERROR: No valid BitzSDD workspaces found (.spec/ が見つからない)", file=sys.stderr)
        return 1

    all_origin_records = []
    for w in workspaces:
        all_origin_records.extend(_origin_records(w / ".spec" / "requirements"))

    results = [collect(w, all_origin_records) for w in workspaces]

    if args.json:
        print(json.dumps({"workspaces": results}, ensure_ascii=False, indent=2))
    else:
        print(render_text(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
