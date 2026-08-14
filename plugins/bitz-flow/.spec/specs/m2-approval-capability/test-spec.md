# M2-2 worktree承認capability テスト仕様

### FLW-NFR-007 repo外parent安全境界

- **対象要件**: FLW-NFR-007
- **導出元種別**: Unwanted Behavior / Event-Driven
- **Verification Method**: unit-test
- **テストケース**: `test_flow_m2_capability.py` の `M2_FLT_010`〜`015`
- **検証内容**: scope転用、期限切れ、nonce再利用、TOCTOU、外部改変を副作用前に拒否する。

### FLW-CON-005 明示的人間承認の責任境界

- **対象要件**: FLW-CON-005
- **導出元種別**: Event-Driven
- **Verification Method**: benchmark
- **M2-2で固定する境界**: capability不在・署名不正・未登録鍵ではwriteを許可しない。
- **後続**: 3platform confirmationはM2-6で検証する。

### FLW-CON-006 cleanupの安全境界

- **対象要件**: FLW-CON-006
- **導出元種別**: Unwanted Behavior
- **Verification Method**: unit-test
- **検証内容**: guard外のdirectory削除・registry改変をORPHANとして検出しquarantineへ接続する。
