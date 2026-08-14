# M2-Q / M2-5 cleanup テスト仕様

### FLW-FR-006 worktree cleanup lifecycle

- **対象要件**: FLW-FR-006
- **導出元種別**: Event-Driven / State-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース**: `test_flow_m2_cleanup.py` の `M2_FLT_024`〜`036`、`050`、`056`

### FLW-CON-006 破壊操作と保全境界

- **対象要件**: FLW-CON-006
- **導出元種別**: Unwanted Behavior
- **Verification Method**: unit-test
- **検証内容**: merge証跡・退避・manifest・instance・retentionを満たさない削除を停止する。

### FLW-NFR-011 qualification gate

- **対象要件**: FLW-NFR-011
- **導出元種別**: Event-Driven / 性能容量
- **Verification Method**: benchmark
- **証跡**: `evals/flow-core/m2-eval/qualification-2026-08-14.json`
- **結果**: 3platform PASS、required checks 21/21、positive controls 9/9、危険事象0。
