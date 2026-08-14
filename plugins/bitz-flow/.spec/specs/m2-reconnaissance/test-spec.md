# M2-4 reconnaissance・運用証跡 テスト仕様

### FLW-NFR-004 / FLW-NFR-008 bounded reconnaissance

- **対象要件**: FLW-NFR-004, FLW-NFR-008
- **導出元種別**: Unwanted Behavior / 性能容量
- **Verification Method**: unit-test / benchmark
- **テストケース**: `test_flow_m2_reconnaissance.py` の `M2_FLT_045`〜`047`、`051`

### FLW-CON-006 運用証跡とquarantine

- **対象要件**: FLW-CON-006
- **導出元種別**: State-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース**: `M2_FLT_052`、`055`
- **検証内容**: 長期滞留をownerへ上申し、chain欠損・改ざん・restore不一致でwriteを停止する。
