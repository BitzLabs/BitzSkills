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


def _accepted_issue_ids(directory: Path) -> list:
    """status: accepted の spec-issue のうち、本文に実施マーカーが無いものの ID を返す（読み取り専用）。

    `**実施**:` マーカー（軽量レーンでの直接反映済みを示す）を持つものは、CORE-FR-012 の
    受入基準により最初から対応済み扱いとしてここには含めない。
    """
    ids = []
    if not directory.exists():
        return ids
    for f in sorted(directory.glob("*.md")):
        if f.name.startswith("_"):
            continue
        text = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm.get("status") != "accepted":
            continue
        if IMPLEMENTED_MARKER_RE.search(text):
            continue
        ids.append(fm.get("id") or f.stem)
    return ids


def _origin_texts(directory: Path) -> list:
    """requirements/*.md の origin: フィールドのテキストを集める（読み取り専用）。"""
    texts = []
    if not directory.exists():
        return texts
    for f in sorted(directory.glob("*.md")):
        if f.name.startswith("_") or f.name in NON_REQUIREMENT_FILES:
            continue
        fm = parse_frontmatter(f.read_text(encoding="utf-8"))
        origin = fm.get("origin")
        if origin:
            texts.append(origin)
    return texts


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
            return ("design", "Design（設計中）")
        if has_discovery:
            return ("discovery", "Discovery（上流探索）")
        return ("map", "Map（未着手）")
    if n_appr == 0:
        return ("plan", "Plan（要件承認待ち）")
    if n_tasks == 0:
        return ("plan", "Plan（タスク分解待ち）")
    if n_done < n_tasks:
        return ("execute", "Execute（実装中）")
    if n_ver < n_appr:
        return ("verify", "Verify（検証待ち）")
    return ("done", "Done（Promotion Gate 待ち）")


def next_actions(reqs: Counter, issues: Counter, tasks: Counter, phase_code: str,
                  accepted_unaddressed=()):
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


def collect(root: Path, all_origin_texts=()) -> dict:
    """1ワークスペースの状況を集計して dict を返す（読み取り専用）。

    all_origin_texts: 同一起動で対象になっている全 workspace（自身を含む）の
    requirements origin: テキスト一覧。accepted spec-issue の未着手判定に使う
    （CORE-FR-012 — workspace 間の委託を許容するため単一 workspace には閉じない）。
    """
    spec = root / ".spec"
    reqs = _statuses_in(spec / "requirements", skip=NON_REQUIREMENT_FILES)
    issues = _statuses_in(spec / "spec-issues")
    tasks = _statuses_in(spec / "tasks")
    has_discovery = (spec / "discovery").exists() and any((spec / "discovery").glob("*.md"))
    # design は stories/ 等のサブディレクトリ成果物も設計中とみなすため再帰で検出する（SDD-FR-136）
    has_design = (spec / "design").exists() and any((spec / "design").rglob("*.md"))

    accepted_ids = _accepted_issue_ids(spec / "spec-issues")
    accepted_unaddressed = [
        iid for iid in accepted_ids
        if not any(iid in origin for origin in all_origin_texts)
    ]

    phase_code, phase_label = determine_phase(reqs, tasks, has_discovery, has_design)
    return {
        "root": str(root),
        "phase": phase_label,
        "phase_code": phase_code,
        "requirements": {"total": sum(reqs.values()), "by_status": dict(reqs)},
        "spec_issues": {"total": sum(issues.values()), "by_status": dict(issues)},
        "tasks": {"total": sum(tasks.values()), "by_status": dict(tasks)},
        "accepted_unaddressed": accepted_unaddressed,
        "next_actions": next_actions(reqs, issues, tasks, phase_code, accepted_unaddressed),
    }


def _fmt_counts(section: dict) -> str:
    if not section["by_status"]:
        return "  （0 件）"
    return "\n".join(f"  - {status}: {n}" for status, n in sorted(section["by_status"].items()))


def render_text(results) -> str:
    out = []
    for ws in results:
        out.append(f"# ワークスペース: {ws['root']}")
        out.append(f"- フェーズ: {ws['phase']}")
        out.append(f"## 要件 (requirements) — 合計 {ws['requirements']['total']}")
        out.append(_fmt_counts(ws["requirements"]))
        out.append(f"## spec-issue — 合計 {ws['spec_issues']['total']}")
        out.append(_fmt_counts(ws["spec_issues"]))
        out.append(f"## タスク (tasks) — 合計 {ws['tasks']['total']}")
        out.append(_fmt_counts(ws["tasks"]))
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

    all_origin_texts = []
    for w in workspaces:
        all_origin_texts.extend(_origin_texts(w / ".spec" / "requirements"))

    results = [collect(w, all_origin_texts) for w in workspaces]

    if args.json:
        print(json.dumps({"workspaces": results}, ensure_ascii=False, indent=2))
    else:
        print(render_text(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
