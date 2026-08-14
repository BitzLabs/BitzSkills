#!/usr/bin/env python3
"""quality_trace.py — bitz-quality 要件トレーサビリティ & 証跡連携スクリプト

.spec/requirements/ の EARS 要件 ID と tests/ 配下のテストを照合し、
トレーサビリティマトリクスおよび検証証跡（verification evidence）を自動生成する。
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def scan_requirements(target_dir: Path) -> list[dict]:
    """要件一覧をスキャンする"""
    reqs = []
    req_dir = target_dir / ".spec/requirements"
    if not req_dir.exists():
        for p in target_dir.glob("plugins/*/.spec/requirements"):
            req_dir = p
            break

    if req_dir.exists():
        for f in sorted(req_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            id_m = re.search(r"^id:\s*([A-Z0-9\-]+)", content, re.MULTILINE)
            status_m = re.search(r"^status:\s*(\w+)", content, re.MULTILINE)
            title_m = re.search(r"^###\s+[A-Z0-9\-]+\s+(.+)$", content, re.MULTILINE)
            
            if id_m:
                rel_f = str(f.relative_to(target_dir)) if target_dir in f.parents else str(f)
                reqs.append({
                    "id": id_m.group(1).strip(),
                    "status": status_m.group(1).strip() if status_m else "draft",
                    "title": title_m.group(1).strip() if title_m else f.stem,
                    "file": rel_f
                })
    return reqs

def scan_tests_for_requirements(target_dir: Path, req_ids: list[str]) -> dict[str, list[dict]]:
    """テストファイル内の要件ID参照をスキャンする"""
    coverage = {rid: [] for rid in req_ids}
    tests_dir = target_dir / "tests"
    if not tests_dir.exists() and (target_dir.parent / "tests").exists():
        tests_dir = target_dir.parent / "tests"
    elif not tests_dir.exists() and (target_dir.parent.parent / "tests").exists():
        tests_dir = target_dir.parent.parent / "tests"
    
    if tests_dir.exists():
        for tf in sorted(tests_dir.glob("test_*.py")):
            content = tf.read_text(encoding="utf-8")
            rel_tf = str(tf.relative_to(target_dir)) if target_dir in tf.parents else str(tf)
            
            for rid in req_ids:
                normalized_id = rid.replace("-", "_")
                if rid in content or normalized_id.lower() in content.lower():
                    coverage[rid].append({
                        "test_file": rel_tf,
                        "match_type": "explicit" if rid in content else "normalized"
                    })
    return coverage

def generate_matrix_markdown(reqs: list[dict], coverage: dict[str, list[dict]]) -> tuple[str, bool, float]:
    covered_count = sum(1 for rid, tests in coverage.items() if len(tests) > 0)
    total_count = len(reqs)
    coverage_rate = (covered_count / total_count * 100) if total_count > 0 else 100.0
    all_covered = (covered_count == total_count)
    
    lines = [
        f"# 要件トレーサビリティマトリクス (Traceability Matrix)",
        f"",
        f"- **生成日時**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **要件カバレッジ**: **{coverage_rate:.1f}%** ({covered_count} / {total_count} 要件)",
        f"- **判定**: **{'PASS ✅' if all_covered else 'INCOMPLETE ⚠️'}**",
        f"",
        f"## 1. 要件 ⇄ 自動テスト対応表",
        f"",
        f"| 要件 ID | ステータス | 要件タイトル | 紐づくテストファイル | 判定 |",
        f"|---|---|---|---|---|",
    ]
    for r in reqs:
        tests = coverage.get(r["id"], [])
        if tests:
            test_links = ", ".join(f"`{t['test_file']}`" for t in tests)
            verdict = "COVERED ✅"
        else:
            test_links = "(未カバー)"
            verdict = "UNCOVERED ❌"
        lines.append(f"| `{r['id']}` | {r['status']} | {r['title']} | {test_links} | {verdict} |")

    lines.extend([
        f"",
        f"## 2. 未カバー要件 (Uncovered Requirements)",
        f"",
    ])
    uncovered = [r for r in reqs if not coverage.get(r["id"])]
    if uncovered:
        for u in uncovered:
            lines.append(f"- ❌ **[{u['id']}]** {u['title']} (`{u['file']}`)")
    else:
        lines.append("- 全要件がテストでカバーされています ✅\n")

    return "\n".join(lines), all_covered, coverage_rate

def main() -> int:
    parser = argparse.ArgumentParser(
        description="要件IDとテストコードのトレーサビリティを照合・検証します。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # verify
    p_verify = subparsers.add_parser("verify", help="トレーサビリティを検証する")
    p_verify.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    p_verify.add_argument("--save", action="store_true", help=".spec/quality/reports/ に保存する")
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    if args.command == "verify":
        reqs = scan_requirements(target_path)
        req_ids = [r["id"] for r in reqs]
        coverage = scan_tests_for_requirements(target_path, req_ids)
        md_output, all_covered, cov_rate = generate_matrix_markdown(reqs, coverage)
        
        if args.save:
            out_dir = target_path / ".spec/quality/reports"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "traceability-matrix.md"
            out_file.write_text(md_output, encoding="utf-8")
            print(f"[判定] {'PASS' if all_covered else 'INCOMPLETE'} (カバレッジ: {cov_rate:.1f}%)")
            print(f"[✔] トレーサビリティマトリクスを保存しました: {out_file}")
        else:
            print(md_output)
            
        return 0 if all_covered else 1

    return 1

if __name__ == "__main__":
    sys.exit(main())
