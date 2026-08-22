---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_approval.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/approval-context-v2.schema.json,tests/test_flow_m2_approval.py
status: pending
---

### plan-digest承認contextを固定する

- **作業内容**: repository identity、target、HEAD/index/worktree snapshot、effects、期限、nonceから
  `operation_id`を導出し、`--confirm`、期限、nonce未使用、context再導出を検査する。
  - M2の承認方式を`plan-digest`へ固定する。
  - `signed-capability`宣言、capability file、鍵registry依存入力は
    `UNSUPPORTED_APPROVAL_MODE`で停止し、無言降格しない。
  - 署名schema、reviewer role、key lifecycleを本境界へ入れない。
- **完了条件**: 正常承認、期限切れ、nonce再利用、context差替え、signed入力拒否でresultと
  Git副作用0件が契約どおりになる。
- **見積り**: FLW-TSK-106と実装PR 1へまとめ、1 sessionを上限とする。
- **実行判定**: pure contract完了後に開始し、暗号鍵管理の再導入要求が出た場合はscope裁定へ戻す。
