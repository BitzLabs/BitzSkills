# M2 Local Safety Profile テスト仕様

## 対象

- **対象要件**: FLW-NFR-014
- **EARS節**: Event-Driven（20 acceptance clauses）
- **導出元種別**: Event-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **検証ステータス**: green証跡の正は`.spec/verification/`とする

## 導出テスト

| EARS応答群 | Given / When / Then | テスト |
|---|---|---|
| plan-digest・期限・nonce・旧承認拒否 | 正規化contextまたは旧signed入力を与えたとき、operation IDを固定するか`UNSUPPORTED`で停止する | `tests/test_flow_m2_contract_kernel.py`, `tests/test_flow_m2_approval.py`, `tests/test_flow_m2_runtime.py` |
| native path・platform support | platform別native componentとfilesystem観測を与えたとき、可逆identityまたは`UNSUPPORTED_FILESYSTEM`を返す | `tests/test_flow_m2_platform_adapter.py`, `tests/test_flow_m2_contract_v2.py` |
| target authority・intent・receipt chain | 同一targetの競合と各publish crashを注入したとき、writer最大1、mutation前receipt、単調chainを維持する | `tests/test_flow_m2_target_transaction.py` |
| bundle・minimum runtime・promotion | bundle member、generation、runtime、active markerを変更したとき、完全なcurrentだけを公開する | `tests/test_flow_m2_minimum_runtime.py`, `tests/test_flow_m2_promotion.py` |
| runtime mutation境界 | plan後のrepository変化、lock競合、storage/crashを注入したとき、write childを単一coordinatorへ限定しclosed failureへ倒す | `tests/test_flow_m2_runtime.py` |
| audit・reconcile | journalとGit snapshotの一致・不一致、同一／異decisionを与えたとき、3値auditと単一closureへ収束する | `tests/test_flow_m2_recovery.py` |
| doctor・audit・verify-receipt・CLI | read操作と停止入力を与えたとき、persistent write 0でclosed operator resultを返し、reconcileだけclosureを許可する | `tests/test_flow_m2_operability.py` |
| 公開受入 | 3 platform fixtureを同一test ID集合で実行したとき、receipt chain、writer数、副作用、partial active、重複closureのhazardが0である | `evals/flow-core/m2-eval/local_confirmation_subject.py`, `tests/test_flow_m2_confirmation.py` |

受入マトリクス各行とE2E edgeのテスト対応は
`skills/flow-core/references/m2-operability-coverage.json`を機械可読な正とする。

## 検収コマンド

共有スクリプト変更のため全suiteを実行する。ただし次の2件は`origin/main`でも再現する既知の
bitz-quality自己診断障害であり、本要件の検収集合から明示除外する。

- `tests/test_quality_measurand.py::test_QLT_FR_014_mutation_self_diagnosis`
- `tests/test_quality_review.py::test_QLT_FR_010_findings_report_and_auto_ledger`

```text
uv run --with pytest pytest -q \
  --deselect tests/test_quality_measurand.py::test_QLT_FR_014_mutation_self_diagnosis \
  --deselect tests/test_quality_review.py::test_QLT_FR_010_findings_report_and_auto_ledger
python3 scripts/release_check.py
python3 scripts/spec inspect --workspace . plugins/* --check-only
python3 evals/flow-core/m2-eval/run_local_confirmation.py --repo . \
  --verify-for-gate evals/flow-core/m2-eval/active-local-confirmation.json
```
