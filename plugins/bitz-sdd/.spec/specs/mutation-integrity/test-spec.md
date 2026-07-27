---
feature: mutation-integrity
status: verified
requirements: SDD-FR-143, SDD-FR-144
design: SDD-DSN-005
---

# 仕様変更の完全性境界 — テスト仕様

## SDD-FR-143

| EARS節 | 導出種別 | verification_method | テスト |
|---|---|---|---|
| 人間裁定必須遷移のTTY・完全一致入力 | Event-Driven / Unwanted Behavior | unit-test | `test_SDD_FR_143_human_transition_requires_interactive_flag`、`test_SDD_FR_143_non_tty_interactive_transition_is_rejected`、`test_SDD_FR_143_interactive_human_can_approve` |
| actorと未検証provenance | Unwanted Behavior | unit-test | `test_SDD_FR_143_actor_rejects_control_characters`、`test_SDD_FR_143_state_contains_canonical_structured_event` |
| 旧flag廃止 | Unwanted Behavior | unit-test | `test_SDD_FR_143_old_by_human_flag_is_rejected` |
| local task前提 | State-Driven | unit-test | `test_SDD_FR_143_implementing_requires_local_task`、`test_SDD_FR_143_verified_rejects_incomplete_local_task`、`test_SDD_FR_143_verified_with_incomplete_local_task_fails` |
| workspace transaction | Unwanted Behavior | unit-test | `tests/test_spec_transaction.py`の`test_SDD_FR_143_*`（active owner中のrecovery拒否を含む） |
| audit event検査 | Unwanted Behavior | unit-test | `test_SDD_FR_143_corrupt_structured_state_event_fails`、`test_SDD_FR_143_incomplete_journal_fails_inspect`、`test_SDD_FR_143_transition_chain_mismatch_fails_inspect`、`test_SDD_FR_143_current_status_must_match_last_event` |

## SDD-FR-144

| EARS節 | 導出種別 | verification_method | テスト |
|---|---|---|---|
| lock取得後の採番と排他的公開 | Event-Driven | unit-test | `test_SDD_FR_144_existing_workspace_lock_fails_without_output`、`test_SDD_FR_144_success_cleans_lock_and_journal` |
| 既存path非上書き | Unwanted Behavior | unit-test | `test_refuses_overwrite` |
| target SHA拘束 | State-Driven / Unwanted Behavior | unit-test | `test_SDD_FR_144_target_ref_preflight_reports_exact_sha`、`test_SDD_FR_144_target_ref_collision_fails`、`test_SDD_FR_144_target_ref_allows_id_preserving_relocation`、`test_SDD_FR_144_target_ref_detects_accepted_origin_disappearance` |
| Plan直列採番 | manual contract | unit-test | `sdd-core/references/lifecycle.md`と`sdd-git/SKILL.md`のrelease前検査 |

## Boundary / Checks / Depends-on

- **boundary**: `skills/sdd-core/scripts/spec_transaction.py`、`spec_trace.py`、`spec_update.py`、
  `spec_scaffold.py`、`spec_inspect.py`、関連テストとlifecycle/sdd-git文書
- **checks**: focused pytest、全pytest、canonical spec inspect、`release_check.py`
- **depends_on**: SDD-DSN-005、SDD-REV-005、SDD-TSK-028〜031
- **検証ステータス**: verified。
- **検証結果（2026-07-27）**:
  - `pytest -q`: 342 passed / 1533 warnings
  - `spec_inspect.py --workspace . plugins/* --check-only`: 全7 workspace PASS
  - `spec_inspect.py --workspace . plugins/* --check-only --target-ref main`:
    全7 workspace PASS、`target_sha=e83c3eb735e5e0fb0325e73c7af4e54bab560c1f`
  - `python3 scripts/release_check.py`: PASS（bitz-sdd 3.0.0、Claude / agy CLI検査のみ環境未導入でSKIP）
