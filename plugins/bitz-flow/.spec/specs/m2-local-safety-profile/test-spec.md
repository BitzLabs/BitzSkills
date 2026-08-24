# M2 Local Safety Profile テスト仕様

## 対象

- **対象要件**: FLW-NFR-014、FLW-FR-006（create/resume是正の受入）
- **EARS節**: Event-Driven（20 acceptance clauses）
- **導出元種別**: Event-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **検証ステータス**: green証跡の正は`.spec/verification/`とする。
  **`verified`昇格条件は`FLW-NFR-014`が正**であり、fixture上の成立では昇格しない。
  再レビューPASS前にPromotion Gateを通さない。

## 導出テスト

**接続**列は fixture 内部の検証か production 経路の実証かを表す（`SI-FLW-090`）。
worktree operation は縮退規則3 で gated であるため、production から実証できるのは
「到達しないこと」と「旧承認方式の即時拒否」に限られる。**fixture 上の成立を
production 接続の完了として扱わない。** 対応の機械可読な正は
`skills/flow-core/references/m2-operability-coverage.json`（`contract_version: 2`）。

| EARS応答群 | Given / When / Then | テスト | 接続 |
|---|---|---|---|
| plan-digest・期限・nonce・旧承認拒否 | 正規化contextまたは旧signed入力を与えたとき、operation IDを固定するか`UNSUPPORTED`で停止する | `tests/test_flow_m2_contract_kernel.py`, `tests/test_flow_m2_approval.py`, `tests/test_flow_m2_runtime.py` | fixture |
| native path・platform support | platform別native componentとfilesystem観測を与えたとき、可逆identityまたは`UNSUPPORTED_FILESYSTEM`を返す | `tests/test_flow_m2_platform_adapter.py`, `tests/test_flow_m2_contract_v2.py` | fixture |
| target authority・intent・receipt chain | 同一targetの競合と各publish crashを注入したとき、writer最大1、mutation前receipt、単調chainを維持する | `tests/test_flow_m2_target_transaction.py` | fixture |
| bundle・minimum runtime・promotion | bundle member、generation、runtime、active markerを変更したとき、完全なcurrentだけを公開する | `tests/test_flow_m2_minimum_runtime.py`, `tests/test_flow_m2_promotion.py` | fixture |
| runtime mutation境界 | plan後のrepository変化、lock競合、storage/crashを注入したとき、write childを単一coordinatorへ限定しclosed failureへ倒す | `tests/test_flow_m2_runtime.py` | fixture |
| audit・reconcile | journalとGit snapshotの一致・不一致、同一／異decisionを与えたとき、3値auditと単一closureへ収束する | `tests/test_flow_m2_recovery.py` | fixture |
| doctor・audit・verify-receipt・CLI | read操作と停止入力を与えたとき、persistent write 0でclosed operator resultを返し、reconcileだけclosureを許可する | `tests/test_flow_m2_operability.py` | fixture |
| 公開受入 | 3 platform fixtureを同一test ID集合で実行したとき、receipt chain、writer数、副作用、partial active、重複closureのhazardが0である | `evals/flow-core/m2-eval/local_confirmation_subject.py`, `tests/test_flow_m2_confirmation.py` | fixture |
| 旧承認経路のproduction拒否 | production既定dispatcherへ旧capability file・宣言・registryを与えたとき、内容を解析せず`UNSUPPORTED` / `unsupported-approval-mode`で閉じる | `tests/test_flow_m2_legacy_approval.py` | **production** |
| worktree operationのgating | production既定dispatcherへ全8 worktree actionを与えたとき、`UNSUPPORTED` / `command-unavailable`を返す | `tests/test_flow_m2_runtime.py::test_worktree_remains_unreachable_from_public_dispatcher`, `tests/test_flow_m2_operability.py::test_all_operability_commands_exist_but_remain_gated_in_production` | **production** |
| 実環境platform probe | 実行中OSのowner-only／world-readable／network filesystemを観測したとき、`SUPPORTED`または理由つき`UNSUPPORTED_FILESYSTEM`を返し例外を送出しない | `tests/test_flow_m2_platform_probe.py` | fixture（linuxのみ実観測。macOS／Windowsは未実走） |
| child timeoutと有限収束 | hangするchild・SIGTERM無視child・出力洪水を与えたとき、budget内にclosed terminal resultへ収束する | `tests/test_flow_m2_liveness.py` | fixture |
| intentのcrash原子性 | 4つのpublish step全点でkillしたとき、intent確定なら必ず有効な緊急receiptが付く | `tests/test_flow_m2_intent_atomicity.py` | fixture |
| recovery分類の陽性陰性 | `DONE`／`QUARANTINED`×snapshot一致／不一致を与えたとき、`QUARANTINED`を`confirmed-complete`へ畳まない | `tests/test_flow_m2_outcome_binding.py` | fixture |
| marker適格性とlock order | marker欠落・別bundle・audit後差替えを与えたとき、closureを0件にし、target lockとpromotion lockを同時保持しない | `tests/test_flow_m2_marker_eligibility.py` | fixture |

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
