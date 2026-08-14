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
- **合格条件**: 3platform PASS、同一test ID集合digest、実worktree runtime check 8/8、
  required check/positive control 100%、hazard/residual 0。
