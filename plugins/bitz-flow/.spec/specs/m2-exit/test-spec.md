# M2-6 remote-delete / local-write confirmation テスト仕様

### FLW-FR-005 remote branch lifecycle

- **対象要件**: FLW-FR-005
- **導出元種別**: Event-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース**: `test_flow_m2_remote_delete.py` の `M2_FLT_037`〜`044`、`048`、`049`、`054`

### FLW-CON-006 remote destructive safety

- **対象要件**: FLW-CON-006
- **導出元種別**: Unwanted Behavior
- **Verification Method**: unit-test
- **検証内容**: 条件なし削除、CAS不成立、到達不能、ABA不検出を安全側に停止する。

### FLW-NFR-011 M2 confirmation

- **対象要件**: FLW-NFR-011
- **導出元種別**: Event-Driven / 性能容量
- **Verification Method**: benchmark
- **harness**: `evals/flow-core/m2-eval/run_local_confirmation.py`
- **対象**: `write_target: local`（stage/commit/fetch/sync/worktree.*）
- **合格条件**: 3platform PASS、同一test ID集合digest、実worktree runtime check が
  **収集件数と同数**（母数は `tests/test_flow_m2_runtime.py` から導出し、定数で固定しない）、
  required check/positive control 100%、hazard/residual 0。
- **note**: 2026-08-15 の裁定で dispatcher の公開集合は M0 read-only 3 operation へ限定された
  （`.spec/reports/decision-2026-08-15-m0-shipping-surface-and-m2-rescope.md`）。
  runtime check には「worktree が公開入口から到達できないこと」の検査を含む。
  `manifest.operations` が未公開 operation を列挙している点は `FLW-REV-016:SYN-005` として未解消。

### FLW-NFR-011 confirmation証跡の契約（SI-FLW-058）

- **導出元種別**: Unwanted Behavior / State-Driven
- **Verification Method**: unit-test
- **テスト**: qualification fingerprint が24時間を過ぎたら confirmation を起動しないこと
  （陽性対照）。期限内なら通ること（陰性対照）。
- **テスト**: manifest の `operations` が出荷表（`cli.PUBLISHED_OPERATIONS`）と一致し、
  未公開 operation とワイルドカードを含まないこと。未公開の実装済み集合は
  `gated_operations` へ分けること。
- **テスト**: `compatibility_key` の入力が認可核（capability / guard / cleanup / recovery）を
  含むこと。`evidence_id` が `compatibility_key` と別値であること。
- **テスト**: manifest が `expires_at`（発行から7日）を宣言すること。
