---
implements: FLW-NFR-014
depends_on: [FLW-TSK-123]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_platform.py,tests/test_flow_m2_operator_action.py,plugins/bitz-flow/docs/runbooks/m2-worktree-quarantine.md,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### 不支持理由へoperator actionを与え非ok契約の欠落を直す

`FLW-REV-028:GP-001`（P1）。実装中に**自分が書いたコードの欠陥**を1件併せて発見した。

- **実測した欠陥**:
  - `acl-not-owner-only`（既定umask 0755のworktree rootが必ず拒否される）に対し、
    公開resultは理由を載せるが**operator actionを持たない**。runbookにも
    worktree root作成手順が無い。gatingを外しても利用者は自力で復帰できない。
  - **`FLW-TSK-116`／`117`で追加した3つのhandlerが非ok契約を満たしていない。**
    `WorktreeUnsupportedPlatformError`／`WorktreeChildTimeoutError`／`ContractError`の
    写像が`R.build_result`を直呼びし`recovery_class`を設定していないため、
    到達すると`ValueError`になる。`FLW-TSK-123`のdispatcher網がこれを
    `UNAVAILABLE` / `result-indeterminate`へ丸めるため**traceback にはならないが、
    意図した具体的なclosed resultが失われる**（網が欠陥を隠していた）。
- **作業内容**:
  - 3つのhandlerを`_simple_result`経由へ変える（`recovery_class`を
    `worktree_cleanup.recovery_for`から自動決定し、`human-stop`なら
    `required_human_input`を強制する既存の仕組みに乗せる）。
  - 不支持理由ごとに**行動可能な**`required_human_input`を生成する。
    `acl-not-owner-only`は対象pathと必要modeを明示する。
  - runbookへworktree root作成手順（owner-only）を追加する。
  - `FLW-DSN-017` §13.2 へ本停止条件を登録する。
- **完了条件**:
  - 3つのhandlerが到達時に例外にならず、意図したcodeとcauseで閉じること。
  - `acl-not-owner-only`のresultが対象pathと必要modeを含むこと。
  - `human-stop`の理由すべてに`required_human_input`が入ること（機械検査）。
  - runbookにworktree root作成手順があること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: dispatcher網は取りこぼしの最後の受け皿であり、
  **個別handlerの契約遵守を代替しない**。網に頼って個別写像を省かない。
