#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime

# タスク status の正規語彙と表示順（spec_update.py の TRANSITIONS["task"] と一致。SDD-FR-139）
TASK_STATUS_ORDER = ("pending", "implementing", "blocked", "done")

# 対訳辞書は sdd-core の spec_labels.py が SSOT だが、スキル自己完結原則により
# 本スキル配下の複製を参照する（両者の一致は release_check.py が機械検証する）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_labels import status_label  # noqa: E402

# 簡易フロントマターパーサ
def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fm = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        # クォート除去
        if val and val[0] in "\"'":
            q = val[0]
            end = val.find(q, 1)
            val = val[1:end] if end != -1 else val[1:]
        else:
            # 非クォート値の YAML インラインコメントを除去（docs_inspect と同挙動）
            val = re.split(r"\s+#", val, 1)[0].strip()
        fm[key] = val
    return None

def extract_title(text: str, req_id: str) -> str:
    """本文の最初の「### <ID> <タイトル>」見出しから ID 以降をタイトルとして返す。"""
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if not m:
            continue
        heading = m.group(1).strip()
        if heading.startswith(req_id):
            title = heading[len(req_id):].strip()
            return title if title else heading
        return heading
    return "No Title"


def generate_report(root_path: Path) -> Path:
    spec_dir = root_path / ".spec"
    reports_dir = root_path / ".spec" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "status-report.md"

    # 1. Discovery 集計
    discovery_dir = spec_dir / "discovery"
    assumptions_file = discovery_dir / "assumptions.md"
    has_discovery = discovery_dir.exists()
    discovery_status = "未初期化"
    if has_discovery:
        discovery_status = "初期化済"
        if assumptions_file.exists():
            content = assumptions_file.read_text(encoding="utf-8")
            if "Go" in content or "Go-Decision" in content:
                discovery_status = "検証ゲート合格 (Go)"
            elif "No-Go" in content:
                discovery_status = "検証ゲート不合格 (No-Go)"

    # 2. Requirements 集計
    req_dir = spec_dir / "requirements"
    req_stats = {"draft": 0, "approved": 0, "implementing": 0, "verified": 0, "promoted": 0}
    total_reqs = 0
    req_details = []
    
    if req_dir.exists():
        for f in req_dir.glob("*.md"):
            # spec_inspect.py の load_requirements と同じ判定基準:
            # _ 始まり・domains.md・README.md と、frontmatter に id が無いファイルは要件ではない
            if f.name.startswith("_") or f.name in ("domains.md", "README.md"):
                continue
            try:
                text = f.read_text(encoding="utf-8")
                fm = parse_frontmatter(text) or {}
                req_id = fm.get("id", "")
                if not req_id:
                    continue
                status = fm.get("status", "draft").lower()
                title = fm.get("title", "") or extract_title(text, req_id)
                if status in req_stats:
                    req_stats[status] += 1
                else:
                    req_stats["draft"] += 1
                total_reqs += 1
                req_details.append((req_id, title, status))
            except Exception:
                pass

    # 3. Design 集計
    design_dir = spec_dir / "design"
    design_files = ["domain-model.md", "api-design.md", "architecture.md"]
    design_status = {}
    has_design = design_dir.exists()
    
    for df in design_files:
        path = design_dir / df
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            design_status[df] = f"あり (最終更新: {mtime})"
        else:
            design_status[df] = "未作成"

    # 4. Review 集計
    reviews_dir = spec_dir / "reviews"
    review_status = "未実施"
    latest_decision = "なし"
    reviews_found = []
    
    if reviews_dir.exists():
        # `_` 始まりは成果物ではない（`_review-synthesis.md` は最新へのビュー。SDD-FR-160）。
        # 数え上げると件数が水増しされ、decision を持たないため PENDING として集計されてしまう
        review_files = [f for f in reviews_dir.glob("*.md") if not f.name.startswith("_")]
        if review_files:
            review_status = f"{len(review_files)} 件のレビューが存在"
            # 最新のレビュー結果を解析
            for rf in review_files:
                try:
                    text = rf.read_text(encoding="utf-8")
                    fm = parse_frontmatter(text) or {}
                    decision = fm.get("decision", "PENDING").upper()
                    reviews_found.append((rf.name, decision))
                    # 最も厳しいステータスを代表とするか、最新のものをとるか
                    if "FAIL" in decision:
                        latest_decision = "FAIL (要再検討)"
                    elif "CONDITIONAL" in decision and "FAIL" not in latest_decision:
                        latest_decision = "CONDITIONAL_PASS (条件付き合格)"
                    elif "PASS" in decision and latest_decision == "なし":
                        latest_decision = "PASS (合格)"
                except Exception:
                    pass

    # 5. Tasks 集計 — 正規語彙（pending / implementing / blocked / done）で集計する（SDD-FR-139）。
    # spec_status.py の _statuses_in と同じ挙動: 語彙外・欠落 status は (none) として立て、
    # 正規区分へ黙って吸収しない（blocked / implementing がレポート上で不可視になるのを防ぐ）。
    # 5.5 人間裁定遷移の経路別集計（SDD-FR-145。spec_status.py と同じ判定）
    decision_counts = {"interactive": 0, "proxy": 0}
    state_file = spec_dir / "STATE.md"
    if state_file.exists():
        for m in re.finditer(r"<!-- sdd-event:([A-Za-z0-9+/=]+) -->",
                             state_file.read_text(encoding="utf-8", errors="replace")):
            try:
                event = json.loads(base64.b64decode(m.group(1), validate=True))
                kind = (event.get("provenance") or {}).get("kind")
            except Exception:
                continue
            if kind == "interactive-confirmation-unverified":
                decision_counts["interactive"] += 1
            elif kind == "agent-proxy-unverified":
                decision_counts["proxy"] += 1

    tasks_dir = spec_dir / "tasks"
    task_counter = Counter()
    if tasks_dir.exists():
        for f in sorted(tasks_dir.glob("*.md")):
            if f.name.startswith("_"):
                continue
            try:
                fm = parse_frontmatter(f.read_text(encoding="utf-8")) or {}
                task_counter[fm.get("status") or "(none)"] += 1
            except Exception:
                pass
    total_tasks = sum(task_counter.values())

    # タスク集計の表示行を組み立てる: 正規語彙を固定順で日本語主併記表示し、
    # 語彙外（(none) 等）は独立区分として末尾に可視化する（正規区分へ吸収しない）。
    task_lines = [
        f'*   **{status_label("task", s)}**: {task_counter.get(s, 0)} 件'
        for s in TASK_STATUS_ORDER
    ]
    for s in sorted(k for k in task_counter if k not in TASK_STATUS_ORDER):
        task_lines.append(f'*   **{status_label("task", s)}**: {task_counter[s]} 件')
    task_section = "\n".join(task_lines)

    # 進捗計算
    progress = 0
    if total_reqs > 0:
        # verified と promoted を完了とみなす
        completed = req_stats["verified"] + req_stats["promoted"]
        progress = int((completed / total_reqs) * 100)

    # 総合ヘルスメトリクス
    # 7. 検証証跡 集計（SDD-FR-154）。`.spec/verification/` が無ければ節ごと出さない
    evidence_dir = spec_dir / "verification"
    evidence_rows = []
    evidence_covered = set()
    evidence_failed = 0
    if evidence_dir.is_dir():
        for f in sorted(evidence_dir.glob("*.json")):
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                evidence_rows.append((f.name, "-", "読取不能", "-"))
                evidence_failed += 1
                continue
            if not isinstance(payload, dict):
                evidence_rows.append((f.name, "-", "形式不正", "-"))
                evidence_failed += 1
                continue
            exit_code = payload.get("exit_code")
            targets = [r for r in (payload.get("requirements") or []) if isinstance(r, str)]
            evidence_covered.update(targets)
            if exit_code != 0:
                evidence_failed += 1
            commit = payload.get("commit") or ""
            evidence_rows.append(
                (f.name, commit[:7] or "-", str(exit_code), ", ".join(targets) or "-")
            )

    health = "GREEN"
    if evidence_failed:
        health = "RED (失敗した検証証跡あり)"
    elif "FAIL" in latest_decision:
        health = "RED (レビュー失敗)"
    elif discovery_status == "検証ゲート不合格 (No-Go)":
        health = "RED (Discovery検証失敗)"
    elif req_stats["draft"] > 0:
        health = "YELLOW (ドラフト状態の要件あり)"

    # レポート書き出し
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report_content = f"""# BitzSDD status-report

生成日時: {now_str}

## 1. 総合サマリー
| メトリクス | 現在のステータス |
| :--- | :--- |
| **総合ヘルス** | **{health}** |
| **要件進捗率 (Verified/Promoted)** | **{progress}%** ({req_stats["verified"] + req_stats["promoted"]} / {total_reqs} 要件) |
| **ディスカバリー状況** | {discovery_status} |
| **設計レビュー結果** | {latest_decision} |

---

## 2. 要件ライフサイクル状況 ({total_reqs} 件)
*   **{status_label("requirement", "draft")}**: {req_stats["draft"]} 件
*   **{status_label("requirement", "approved")}**: {req_stats["approved"]} 件
*   **{status_label("requirement", "implementing")}**: {req_stats["implementing"]} 件
*   **{status_label("requirement", "verified")}**: {req_stats["verified"]} 件
*   **{status_label("requirement", "promoted")}**: {req_stats["promoted"]} 件

### 要件一覧
| 要件ID | タイトル | ステータス |
| :--- | :--- | :--- |
"""
    if req_details:
        for r_id, r_title, r_status in sorted(req_details):
            report_content += f"| {r_id} | {r_title} | {status_label('requirement', r_status)} |\n"
    else:
        report_content += "| - | 要件が登録されていません | - |\n"

    report_content += f"""
---

## 3. 設計確立状況 (.spec/design/)
*   **ドメインモデル (domain-model.md)**: {design_status.get("domain-model.md", "未作成")}
*   **API設計 (api-design.md)**: {design_status.get("api-design.md", "未作成")}
*   **アーキテクチャ設計 (architecture.md)**: {design_status.get("architecture.md", "未作成")}

---

## 4. レビュー状況 (.spec/reviews/)
*   **統合ステータス**: {review_status}
*   **判定結果**: {latest_decision}

### レビュー報告書一覧
| ファイル名 | レビュー判定 |
| :--- | :--- |
"""
    if reviews_found:
        for rf_name, rf_dec in reviews_found:
            report_content += f"| {rf_name} | `{rf_dec}` |\n"
    else:
        report_content += "| - | レビュー報告書がありません | |\n"

    report_content += f"""
---

## 5. タスク実行状況 (.spec/tasks/ - {total_tasks} 件)
{task_section}

---

## 6. 人間裁定遷移の経路別内訳 (STATE.md)
*   **対話確認経路 (interactive-confirmation-unverified)**: {decision_counts["interactive"]} 件
*   **代行可視化経路 (agent-proxy-unverified)**: {decision_counts["proxy"]} 件

※ 代行遷移は decision-ref（裁定所在参照）を持つ。Promotion Gate で参照先の裁定を人間が確認すること。
"""

    if evidence_dir.is_dir():
        report_content += f"""
---

## 7. 検証証跡 (.spec/verification/ - {len(evidence_rows)} 件)
*   **証跡が覆う要件**: {len(evidence_covered)} 件
*   **失敗・不正な証跡**: {evidence_failed} 件

| 証跡ファイル | commit | exit_code | 対象要件 |
| :--- | :--- | :--- | :--- |
"""
        if evidence_rows:
            for e_name, e_commit, e_exit, e_targets in evidence_rows:
                report_content += f"| {e_name} | `{e_commit}` | {e_exit} | {e_targets} |\n"
        else:
            report_content += "| - | - | - | 証跡がありません |\n"
        report_content += (
            "\n※ 実行時間は observed（非正規の観測値）であり、本表の判定には使わない。"
            "green 判定の正は exit_code と件数（SDD-FR-151）。\n"
        )

    report_file.write_text(report_content, encoding="utf-8")
    return report_file

def main():
    ap = argparse.ArgumentParser(description="Generate status report from .spec")
    ap.add_argument("root", help="Repository root path")
    args = ap.parse_args()
    
    root_path = Path(args.root).resolve()
    report_file = generate_report(root_path)
    print(f"SUCCESS: Report generated at {report_file}")

if __name__ == "__main__":
    main()
