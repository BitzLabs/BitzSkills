# M2-3 create・resume・audit テスト仕様

### FLW-FR-006 worktree lifecycle

- **対象要件**: FLW-FR-006
- **導出元種別**: Event-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース**: `test_flow_m2_worktree.py` の `M2_FLT_016`〜`020`、`053`

### FLW-FR-007 branch/worktree audit

- **対象要件**: FLW-FR-007
- **導出元種別**: State-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース**: `M2_FLT_020`〜`023`
- **検証内容**: dirty/legacy/不定状態を推測せず直交enumへ分類し、三者の閉集合を照合する。

### FLW-NFR-007 repo外parent安全境界

- **対象要件**: FLW-NFR-007
- **導出元種別**: Optional / Unwanted Behavior
- **Verification Method**: unit-test
- **検証内容**: lifecycle capability不足rootではcreate/resumeをUNSUPPORTEDにしauditのみ許可する。
