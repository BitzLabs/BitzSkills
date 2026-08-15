#!/usr/bin/env python3
"""M2 是正枠の実績を run manifest へ追記する（`SI-FLW-058` の先行履行）。

`FLW-REV-016:SYN-015` — ROADMAP は「実績 PR 数・session 数・レビュー修正回数・
出口未達理由を run manifest へ記録する」と定めているが、M2 では1件も記録されておらず、
2026-08-15 の予算裁定で session 上限に根拠を置けなかった。本ツールはその是正であり、
2026-08-15 の裁定でM2是正枠の**着手条件**とされた
（`.spec/reports/decision-2026-08-15-m2-remediation-budget.md`）。

追記のみで既存 entry を書き換えない。予算の消費状況は `--summary` で読む。
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

MANIFEST = Path(__file__).with_name("run-manifest-m2-remediation.json")

#: 2026-08-15 裁定の先行承認枠。到達したら自動停止し人間へ再提示する。
BUDGET_PR = 4
BUDGET_SESSION = 13


def _load() -> dict:
    if not MANIFEST.exists():
        return {
            "schema": "bitz-flow/m2-remediation-run-manifest/v1",
            "budget": {"pr": BUDGET_PR, "session": BUDGET_SESSION,
                       "decision_ref": ".spec/reports/decision-2026-08-15-m2-remediation-budget.md"},
            "entries": [],
        }
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _summary(manifest: dict) -> dict:
    entries = manifest["entries"]
    used_pr = len({entry["pr"] for entry in entries})
    used_session = sum(entry["sessions"] for entry in entries)
    return {
        "used_pr": used_pr,
        "used_session": used_session,
        "budget_pr": manifest["budget"]["pr"],
        "budget_session": manifest["budget"]["session"],
        "exhausted": used_pr >= manifest["budget"]["pr"]
        or used_session >= manifest["budget"]["session"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="M2是正枠の実績をrun manifestへ追記する")
    parser.add_argument("--pr", type=int, help="PR 番号（実装 PR のみ。裁定・調査は budget 外）")
    parser.add_argument("--issue", help="対象 spec-issue（例: SI-FLW-061）")
    parser.add_argument("--sessions", type=int, default=1, help="この PR で消費した session 数")
    parser.add_argument("--review-fixes", type=int, default=0, help="レビュー指摘による修正回数")
    parser.add_argument("--unmet", default="", help="出口未達理由（残っていれば記す）")
    parser.add_argument("--summary", action="store_true", help="消費状況だけを出力する")
    args = parser.parse_args()

    manifest = _load()
    if args.summary:
        print(json.dumps(_summary(manifest), ensure_ascii=False, indent=2))
        return 0
    if args.pr is None or not args.issue:
        parser.error("--pr と --issue は追記時に必須（読み取りだけなら --summary）")

    manifest["entries"].append({
        "pr": args.pr,
        "issue": args.issue,
        "sessions": args.sessions,
        "review_fixes": args.review_fixes,
        "unmet_exit_reason": args.unmet,
        "recorded_at": date.today().isoformat(),
    })
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = _summary(manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["exhausted"]:
        print("予算到達: 停止して人間へ再提示すること（2026-08-15 裁定の付帯条件3）")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
