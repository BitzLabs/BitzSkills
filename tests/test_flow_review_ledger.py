"""SI-FLW-091 — レビュー台帳（FLW-REV-*.json）の整合を機械検査する。

`FLW-REV-027` は、過去 9 レビューの未解決 P0/P1 が機械台帳上 88 件ある一方で後続
レビューが `PASS` を出しており、台帳と判定が食い違って見えると指摘した。

実測すると `carried_over`（88 件）は先行レビューの未解決 P0/P1 と**完全に一致**して
おり、生成そのものは正しかった。問題は **その一致を検査する仕組みが無い** ことである。
台帳がずれても誰も気づかず、`carried_over` から未解決項目が落ちても緑のままになる。

本テストはその欠落を塞ぐ。**resolved 化には実在する証跡を要求する**ため、証跡なしに
台帳を綺麗に見せることはできない。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "plugins" / "bitz-flow" / ".spec"
REVIEWS = SPEC / "reviews"

#: finding が取りうる status。
KNOWN_STATUSES = {"open", "tracked", "resolved"}

#: 台帳へ持ち越す対象の優先度。
CARRIED_PRIORITIES = {"P0", "P1"}


def _review_id_number(path: Path) -> int:
    return int(path.stem.rsplit("-", 1)[1])


def _reviews() -> list[tuple[Path, dict]]:
    items = []
    for path in sorted(REVIEWS.glob("FLW-REV-*.json"), key=_review_id_number):
        items.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return items


REVIEW_FILES = [path for path, _ in _reviews()]
LATEST_PATH, LATEST = _reviews()[-1]


def _findings(review: dict) -> list[dict]:
    return review.get("findings") or []


def _unresolved_before(latest_id: str) -> set[str]:
    """最新レビューより前の、未解決（open / tracked）P0/P1 の ID 集合。"""
    unresolved = set()
    for _, review in _reviews():
        if review["review_id"] == latest_id:
            continue
        for finding in _findings(review):
            if (finding.get("priority") in CARRIED_PRIORITIES
                    and finding.get("status") in {"open", "tracked"}):
                unresolved.add(finding["id"])
    return unresolved


# --- status 語彙 -------------------------------------------------------------


@pytest.mark.parametrize("path", REVIEW_FILES, ids=lambda p: p.stem)
def test_every_finding_declares_a_known_status(path):
    """status が既知の語彙であること（未宣言を黙認しない）。

    `schema_version` を持たないレビューは `status` field の導入前に記録されたもので、
    後から status を付けると履歴の書き換えになる。免除するが、その免除が重要な
    項目を隠していないことは `test_pre_schema_reviews_contain_no_p0_p1` が保証する。
    """
    review = json.loads(path.read_text(encoding="utf-8"))
    if review.get("schema_version") is None:
        pytest.skip("status field 導入前の記録（履歴として保持する）")
    unknown = [
        f"{f.get('id')}={f.get('status')}"
        for f in _findings(review)
        if f.get("status") not in KNOWN_STATUSES
    ]
    assert not unknown, f"{path.name}: 未知または未宣言の status {unknown}"


@pytest.mark.parametrize("path", REVIEW_FILES, ids=lambda p: p.stem)
def test_pre_schema_reviews_contain_no_p0_p1(path):
    """status 免除が P0/P1 を隠していないこと。

    免除された記録に P0/P1 があると、未解決のまま carried_over からも漏れる。
    免除の範囲を P2 以下に限ることで、その穴を塞ぐ。
    """
    review = json.loads(path.read_text(encoding="utf-8"))
    if review.get("schema_version") is not None:
        pytest.skip("status を宣言する契約下のレビュー")
    hidden = [
        f["id"] for f in _findings(review)
        if f.get("priority") in CARRIED_PRIORITIES
    ]
    assert not hidden, (
        f"{path.name}: status 免除の記録に P0/P1 がある。免除できない {hidden}"
    )


@pytest.mark.parametrize("path", REVIEW_FILES, ids=lambda p: p.stem)
def test_every_finding_declares_a_priority(path):
    """優先度が無いと carried_over の判定から静かに漏れる。"""
    review = json.loads(path.read_text(encoding="utf-8"))
    missing = [f.get("id") for f in _findings(review) if not f.get("priority")]
    assert not missing, f"{path.name}: priority が無い finding {missing}"


# --- carried_over の厳密一致 -------------------------------------------------


def test_latest_review_carries_over_every_unresolved_p0_p1():
    """**本 issue の中心**。未解決 P0/P1 が carried_over から欠落しないこと。"""
    carried = set(LATEST.get("carried_over") or [])
    unresolved = _unresolved_before(LATEST["review_id"])
    missing = sorted(unresolved - carried)
    assert not missing, (
        f"{LATEST_PATH.name}: 未解決 P0/P1 が carried_over から欠落している {missing}"
    )


def test_latest_review_does_not_carry_over_resolved_findings():
    """既に resolved のものを持ち越して未解決件数を水増ししないこと。"""
    carried = set(LATEST.get("carried_over") or [])
    unresolved = _unresolved_before(LATEST["review_id"])
    extra = sorted(carried - unresolved)
    assert not extra, (
        f"{LATEST_PATH.name}: 未解決でない finding を carried_over に含めている {extra}"
    )


def test_carried_over_entries_reference_real_findings():
    """carried_over の ID が実在する finding を指すこと。"""
    known = {
        finding["id"]
        for _, review in _reviews()
        for finding in _findings(review)
    }
    unknown = sorted(set(LATEST.get("carried_over") or []) - known)
    assert not unknown, f"carried_over が実在しない finding を指している {unknown}"


# --- tracked / resolved の証跡 -----------------------------------------------


@pytest.mark.parametrize("path", REVIEW_FILES, ids=lambda p: p.stem)
def test_tracked_findings_reference_a_real_issue_or_gate_precondition(path):
    """`tracked` は追跡先を持ち、それが実在すること。

    追跡先が消えた（または最初から無い）まま `tracked` を名乗ると、未解決項目が
    誰にも追われないまま台帳上は追跡中に見える。
    """
    review = json.loads(path.read_text(encoding="utf-8"))
    gate_ids = {
        item["id"] if isinstance(item, dict) else str(item)
        for item in (review.get("gate_preconditions") or [])
    }
    problems = []
    for finding in _findings(review):
        if finding.get("status") != "tracked":
            continue
        target = finding.get("tracked_by")
        if not target:
            problems.append(f"{finding['id']}: tracked_by が無い")
            continue
        for ref in (target if isinstance(target, list) else [target]):
            ref = str(ref)
            if ref.startswith("SI-FLW-"):
                if not (SPEC / "spec-issues" / f"{ref}.md").exists():
                    problems.append(f"{finding['id']}: spec-issue 不在 {ref}")
            elif ":GP-" in ref:
                review_id, _, _ = ref.partition(":")
                other = REVIEWS / f"{review_id}.json"
                if not other.exists():
                    problems.append(f"{finding['id']}: レビュー不在 {ref}")
            else:
                problems.append(f"{finding['id']}: 追跡先の形式が不明 {ref}")
    assert not problems, f"{path.name}: {problems}"


@pytest.mark.parametrize("path", REVIEW_FILES, ids=lambda p: p.stem)
def test_resolved_findings_cite_evidence(path):
    """`resolved` 化には実在する修正・検証証跡を要求する（`SI-FLW-091`）。

    証跡を求めないと、台帳を綺麗に見せるためだけの resolved 化ができてしまう。
    これは `FLW-REV-027` が指摘した過大主張そのものである。

    既存の履歴（本 test 導入前に resolved 化された finding）は `resolved_by` を
    持たないため、**導入後に新しく resolved 化するものだけ**を対象にする。
    移行の境界は `ledger_contract` フィールドで宣言する。
    """
    review = json.loads(path.read_text(encoding="utf-8"))
    if not review.get("ledger_contract"):
        pytest.skip("台帳契約の宣言前に記録されたレビュー（履歴として保持する）")
    problems = []
    for finding in _findings(review):
        if finding.get("status") != "resolved":
            continue
        evidence = finding.get("resolved_by")
        if not evidence:
            problems.append(f"{finding['id']}: resolved なのに resolved_by が無い")
            continue
        for ref in (evidence if isinstance(evidence, list) else [evidence]):
            ref = str(ref)
            if ref.startswith("tests/") or ref.startswith("plugins/"):
                target = ROOT / ref.partition("::")[0]
                if not target.exists():
                    problems.append(f"{finding['id']}: 証跡不在 {ref}")
            elif ref.startswith("FLW-TSK-"):
                if not (SPEC / "tasks" / f"{ref}.md").exists():
                    problems.append(f"{finding['id']}: task 不在 {ref}")
    assert not problems, f"{path.name}: {problems}"
