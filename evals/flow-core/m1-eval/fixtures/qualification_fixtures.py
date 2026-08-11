"""3 platform 分の qualification fixture（FLW-NFR-011）。

各 platform の adapter が返す observation を模した**固定入力**である。実 CLI は起動しない
（実接続は M1-6 confirmation）。ここで確かめたいのは被測定物の性質ではなく、
**harness が 3 platform すべてで同じ判定に収束するか**である。

fixture を「常に PASS する都合のよい入力」にしないため、破損系の派生
（`corrupt_variant` / `residual_variant` / `undetected_control_variant`）も併せて提供する。
"""

from __future__ import annotations

import sys
from pathlib import Path

_M1_EVAL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_M1_EVAL))
sys.path.insert(0, str(_M1_EVAL.parents[2] / "plugins" / "bitz-flow" / "skills" / "flow-core" / "scripts"))

import qualification as Q  # noqa: E402
from flowlib import result as R  # noqa: E402

#: platform ごとの CLI / model / event-contract identity。
PLATFORM_IDENTITY = {
    "claude": {
        "cli_identity": "claude-code",
        "model_identity": "claude-opus-5",
        "host_event_contract": "claude/event-contract/v1",
    },
    "codex": {
        "cli_identity": "codex-cli",
        "model_identity": "gpt-5.4-codex",
        "host_event_contract": "codex/event-contract/v1",
    },
    "antigravity": {
        "cli_identity": "agy",
        "model_identity": "gemini-3-pro",
        "host_event_contract": "antigravity/event-contract/v1",
    },
}

#: trial 種別ごとの必須 check と陽性対照。結果取得より前に拘束する閉じた集合。
TRIAL_CHECKS = {
    "Q-NORMAL": {
        "required": ("CHK-CLI-MATCH", "CHK-EVENT-MATCH", "CHK-ENVELOPE-SCHEMA", "CHK-EXIT-CODE"),
        "controls": ("PC-NORMAL-ENVELOPE",),
    },
    "Q-REJECT": {
        "required": ("CHK-FAILURE-CODE", "CHK-ORACLE-DETECT"),
        "controls": ("PC-REJECT-KNOWN-FAILURE", "PC-REJECT-ORACLE"),
    },
    "Q-CORRUPT": {
        "required": ("CHK-EVENT-MISSING", "CHK-FLUSH-FAILURE", "CHK-SCHEMA-CONFLICT"),
        "controls": ("PC-CORRUPT-BLOCKED",),
    },
}


def _digest(*parts: str) -> str:
    return R.sha256_of(R.canonical_bytes(list(parts)))


def trial(platform: str, operation: str, kind: str) -> Q.TrialOutcome:
    """PASS する trial の観測結果。"""
    identity = PLATFORM_IDENTITY[platform]
    spec = TRIAL_CHECKS[kind]
    fixture = _digest(platform, operation, kind, "initial")
    return Q.TrialOutcome(
        kind=kind,
        credential_class="local-only",
        capability=("git>=2.30", "atomic-rename", "advisory-lock", "process-tree-convergence"),
        fixture_initial_digest=fixture,
        fixture_final_digest=fixture,
        sandbox_boundary=f"qual-{platform}-{operation.replace('.', '-')}-{kind.lower()}-fixture",
        raw_log_digest=_digest(platform, operation, kind, "raw-log"),
        oracle_digest=_digest(kind, "oracle"),
        required_check_ids=spec["required"],
        checks=tuple(Q.CheckResult(check_id, 1, 1) for check_id in spec["required"]),
        positive_control_ids=spec["controls"],
        positive_controls_detected=spec["controls"],
        residual_side_effects=(),
        hazardous_events=(),
        **identity,
    )


def trials(platform: str, operation: str = "git.commit") -> list[Q.TrialOutcome]:
    return [trial(platform, operation, kind) for kind in Q.TRIAL_KINDS]


# --- 破損系の派生（fixture が甘くないことを示すため）---------------------------


def corrupt_variant(platform: str, operation: str = "git.commit") -> list[Q.TrialOutcome]:
    """Q-CORRUPT の必須 check の1つを denominator 0 にした派生。"""
    outcomes = trials(platform, operation)
    broken = outcomes[2]
    checks = list(broken.checks)
    checks[0] = Q.CheckResult(checks[0].check_id, 0, 0)
    outcomes[2] = dataclasses_replace(broken, checks=tuple(checks))
    return outcomes


def residual_variant(platform: str, operation: str = "git.commit") -> list[Q.TrialOutcome]:
    """fixture が初期状態へ戻っていない派生。"""
    outcomes = trials(platform, operation)
    outcomes[0] = dataclasses_replace(
        outcomes[0],
        fixture_final_digest=_digest(platform, operation, "Q-NORMAL", "dirty"),
        residual_side_effects=("remote branch qual-tmp が残っている",),
    )
    return outcomes


def undetected_control_variant(platform: str, operation: str = "git.commit") -> list[Q.TrialOutcome]:
    """陽性対照を検出できなかった派生（oracle が壊れている状態）。"""
    outcomes = trials(platform, operation)
    outcomes[1] = dataclasses_replace(outcomes[1], positive_controls_detected=())
    return outcomes


def dataclasses_replace(outcome: Q.TrialOutcome, **changes) -> Q.TrialOutcome:
    import dataclasses

    return dataclasses.replace(outcome, **changes)
