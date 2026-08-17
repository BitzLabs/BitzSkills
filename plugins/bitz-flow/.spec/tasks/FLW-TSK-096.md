---
implements: FLW-CON-007
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/schemas/result-v1.schema.json, plugins/bitz-flow/skills/flow-core/scripts/flowlib/result.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/intent.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_cleanup.py, plugins/bitz-flow/.spec/design/FLW-DSN-016.md
status: done
---

### enum 契約の単一の正を schema と実装定数へ固定する

- **作業内容**: `FLW-DSN-016` §2 の閉集合表・所在表を実体へ反映し、照合可能な状態を作る。
  - `result-v1.schema.json` の `$defs/cause` へ `quarantined` を追加する。実装定数
    `ALLOWED_CAUSES` にだけ存在して公開 schema に無い状態を解消する（`ORPHAN` と同型の逸脱）。
  - `result-v1.schema.json` へ `$defs/release_class`（`worktree-not-started` /
    `worktree-resumable` / `worktree-confirmed-done` / `worktree-unresolved`）を新設する。
    公開 result の `data.quarantine` に出ている値が schema を持たない状態を解消する。
  - 実装側に集合定数を新設する。`intent.py` へ `INTENT_RECORD_STATES`、
    `result.py` へ `GATE_STATUSES` / `ATTEMPT_STATUSES` / `TRIAL_KINDS`、
    `worktree_cleanup.py` へ `RELEASE_CLASSES`。いずれも値を個別文字列として散らしたまま
    集合を持たない現状では照合不能である。既存の個別定数は集合定数から導くか、
    集合定数を唯一の列挙元にして重複定義を作らない。
  - `classify_quarantine` の戻り値を `RELEASE_CLASSES` の要素に限定する。
- **範囲外**: 照合テストの実装（後続タスク）。分類ロジックの是正（後続タスク）。
- **検証**: 新設した集合定数が schema の enum と一致すること、`build_result` が
  `cause: "quarantined"` を schema 検証込みで通すこと、既存の全 pytest が green であること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
