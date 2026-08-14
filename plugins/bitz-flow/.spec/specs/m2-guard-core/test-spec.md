# M2-1 guard core テスト仕様

### FLW-NFR-006 同一host writeの直列化

- **対象要件**: FLW-NFR-006
- **導出元種別**: Event-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース**: `test_flow_m2_guard.py` の `M2_FLT_001`〜`009`、`057`
- **検証内容**: canonical順、index包含、同一key最大mutation 1、stable identity、case/Unicode alias収束。

### FLW-CON-005 明示的人間承認の責任境界

- **対象要件**: FLW-CON-005
- **導出元種別**: Event-Driven
- **Verification Method**: benchmark
- **M2-1で固定する境界**: root identity差し替えでguard keyが変化し、旧承認を再利用できないこと。
- **後続**: capability署名と3platform benchmarkはM2-2で検証する。

### FLW-CON-006 cleanupの安全境界

- **対象要件**: FLW-CON-006
- **導出元種別**: Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース**: binding不一致、path escape、portable path aliasを副作用前に拒否する負のfixture。
