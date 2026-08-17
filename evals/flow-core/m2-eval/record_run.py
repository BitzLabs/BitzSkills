#!/usr/bin/env python3
"""M2 是正の実績を run manifest へ追記する。

`SI-FLW-074` の reconciliation snapshot 以後、記録は append-only である。同じ PR を
二重記録せず、session 数が不明な過去 entry は推測で補完しない。2026-08-16 の裁定で
FLW-REV-018 の是正上限は解除されたため、この記録器は旧 budget による自動停止をしない。
次期予算の再校正は `FLW-REV-019:GP-006` の人間裁定を待つ。
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


MANIFEST = Path(__file__).with_name("run-manifest-m2-remediation.json")
UNBOUNDED_DECISION = ".spec/reports/decision-2026-08-16-flw-rev-018-remediation.md"
RECALIBRATION_REF = "FLW-REV-019:GP-006"
M2_EXCEPTION_SCOPE = "M2 remediation / FLW-REV-018"
M2_EXCEPTION_DECISION = ".spec/reports/decision-2026-08-17-si-flw-076-m2-budget-exception.md"


def _default_manifest() -> dict:
    return {
        "schema": "bitz-flow/m2-remediation-run-manifest/v2",
        "budget": {
            "mode": "unbounded",
            "scope": M2_EXCEPTION_SCOPE,
            "decision_ref": UNBOUNDED_DECISION,
            "exception_ref": M2_EXCEPTION_DECISION,
            "recalibration_pending": RECALIBRATION_REF,
        },
        "entries": [],
    }


def _validate(manifest: dict) -> None:
    budget = manifest.get("budget", {})
    if budget.get("mode") != "unbounded":
        raise ValueError("現行のM2是正裁定は unbounded budget でなければならない")
    if budget.get("scope") != M2_EXCEPTION_SCOPE:
        raise ValueError("上限なしは M2 remediation / FLW-REV-018 にだけ適用できる")
    if budget.get("decision_ref") != UNBOUNDED_DECISION:
        raise ValueError("上限解除の裁定参照が一致しない")
    if budget.get("exception_ref") != M2_EXCEPTION_DECISION:
        raise ValueError("M2限定例外の裁定参照が一致しない")
    if budget.get("recalibration_pending") != RECALIBRATION_REF:
        raise ValueError("次期予算の再校正参照が一致しない")

    prs = [entry.get("pr") for entry in manifest.get("entries", [])]
    if len(prs) != len(set(prs)):
        raise ValueError("同じPR番号を重複記録している")


def _load() -> dict:
    manifest = _default_manifest() if not MANIFEST.exists() else json.loads(MANIFEST.read_text(encoding="utf-8"))
    _validate(manifest)
    return manifest


def _summary(manifest: dict) -> dict:
    entries = manifest["entries"]
    known_sessions = sum(entry["sessions"] for entry in entries if entry["sessions"] is not None)
    unknown_session_prs = [entry["pr"] for entry in entries if entry["sessions"] is None]
    return {
        "used_pr": len(entries),
        "known_session": known_sessions,
        "unknown_session_prs": unknown_session_prs,
        "budget_mode": manifest["budget"]["mode"],
        "exception_scope": manifest["budget"]["scope"],
        "recalibration_pending": manifest["budget"]["recalibration_pending"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="M2是正の実績をrun manifestへ追記する")
    parser.add_argument("--pr", type=int, help="PR 番号（実装 PR のみ。裁定・調査は budget 外）")
    parser.add_argument("--issue", help="対象 spec-issue またはレビュー ID")
    parser.add_argument("--sessions", type=int, help="この PR で消費した session 数（新規記録では必須）")
    parser.add_argument("--review-fixes", type=int, default=0, help="レビュー指摘による修正件数")
    parser.add_argument("--unmet", default="", help="出口未達理由（残っていれば記す）")
    parser.add_argument("--summary", action="store_true", help="消費状況だけを出力する")
    args = parser.parse_args()

    try:
        manifest = _load()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.summary:
        print(json.dumps(_summary(manifest), ensure_ascii=False, indent=2))
        return 0
    if args.pr is None or not args.issue or args.sessions is None:
        parser.error("--pr、--issue、--sessions は追記時に必須（読み取りだけなら --summary）")
    if args.sessions < 0 or args.review_fixes < 0:
        parser.error("--sessions と --review-fixes は0以上でなければならない")
    if args.pr in {entry["pr"] for entry in manifest["entries"]}:
        parser.error(f"PR #{args.pr} はすでに記録済み")

    manifest["entries"].append({
        "pr": args.pr,
        "issue": args.issue,
        "sessions": args.sessions,
        "review_fixes": args.review_fixes,
        "unmet_exit_reason": args.unmet,
        "recorded_at": date.today().isoformat(),
    })
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_summary(manifest), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
