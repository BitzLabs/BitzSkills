---
implements: FLW-FR-006
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,tests/test_flow_m2_legacy_approval.py,tests/test_flow_m1_contract_rows.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/skills/flow-core/references/operation-catalog.md,plugins/bitz-flow/skills/flow-core/SKILL.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### create/resume CLIをplan-digest専用契約へ一致させる

`SI-FLW-085`（`FLW-REV-027:SYN-002` P0）。`FLW-DSN-017` §2はM2の承認契約を
plan-digestへ統一したが、`_op_worktree`のcreate/resume経路は廃止済みの
signed-capability契約と旧contextを参照したままである。

- **実測した欠陥**:
  - `cli.py`が`resolve_approval_mode`でsigned-capability／plan-digestを分岐し、
    `signed_mode`のとき`--capability-file`を要求して内容をJSON解析する。
  - `cli.py` L771が`plan_value.context.worktree_dir_guard_key`を参照するが、
    `plan_value.context`は`ApprovalContext`であり当該fieldを持たない。**AttributeErrorになる。**
    現状は手前の`plan()`が`platform evidence is required`で送出するため露見していない
    （`SI-FLW-084`を先に直すと顕在化する）。
  - `_op_worktree`のL593以降の`audit`分岐はL591で先に
    `_op_worktree_operability`へ委譲されるため**到達不能**であり、その中だけが
    legacy `worktree_capability`をproduction handlerから参照している。
  - 同等の共通preflight`worktree_operability.has_unsupported_approval_input`は
    既に存在し、doctor／audit／verify-receipt／reconcileでは使われているが、
    create／resumeでは使われていない。
- **作業内容**:
  - create/resume経路の承認分岐を除去し、共通preflightへ一本化する。旧宣言・
    capability file・trusted key registryの検出は**内容を解析せず**mutation前に
    `UNSUPPORTED` + `unsupported-approval-mode`へ閉じる。
  - `resolve_approval_mode`、`signed_mode`分岐、`capability_from_json`呼び出し、
    `--capability-file`必須判定をCLIから除去する。
  - `worktree_dir_guard_key`参照を`ApprovalContext.target_collision_key`へ置換する。
  - 到達不能な`audit`分岐を除去し、`worktree_capability`のproduction handlerからの
    参照を0件にする（module自体は残す）。
  - `FLW-DSN-017` §13.6 legacy exclusion表のnegative test ID欄を、実在する
    production起点testで埋める。
- **完了条件**:
  - production既定dispatcher（`flow.py`別process起動）を起点とするnegative testが、
    旧宣言・capability file・registryのそれぞれで`UNSUPPORTED` /
    `unsupported-approval-mode`を返すこと。
  - `cli.py`に`resolve_approval_mode`／`capability_from_json`／`worktree_dir_guard_key`／
    `worktree_capability`の参照が0件であること（機械検査）。
  - `plan-digest`への暗黙のfallbackと、旧入力の内容解析が発生しないこと。
  - 全suite green。`FLW-CON-008`の`tests/test_flow_design_completion_contract.py`が
    §13.6の埋めたtest IDを実在と認めること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: `SI-FLW-084`より先行する。platform evidenceを結線すると
  `worktree_dir_guard_key`のAttributeErrorが顕在化するため、順序を入れ替えない。
