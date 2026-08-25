---
implements: FLW-NFR-014
depends_on: [FLW-TSK-126]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,tests/test_flow_m2_operation_budget.py,tests/test_flow_m2_liveness.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### operation全体deadlineとsnapshot出力上限を設計値化する

`FLW-REV-028:GP-002`（P1）。`SYN-002`（codex）と`SYN-011`（agy／codex）の統合。

- **実測した欠陥**:
  - **operation全体のdeadlineが無い。** `_supervised_git`はchild単位のbudgetしか持たず、
    1 operationは`snapshot()`（4 child）を plan／apply／post で複数回回すため
    **15〜20 child**を起動する。child毎30秒なら最悪450秒超であり、
    `FLW-NFR-014`が要求する**30秒terminal result**は成立しない。
    §13.4 は operation 全体 300 秒と reconciliation reserve を掲げるが実装が無い。
  - **snapshot経路の出力上限が既定値の流用である。** `_supervised_git`は
    `output_limit_bytes`を渡さず`process.DEFAULT_OUTPUT_LIMIT_BYTES`（8 MiB）を使う。
    `git status --porcelain=v2 -z --untracked-files=all`は未追跡ファイルが多い repository で
    これを超えうる（porcelain=v2 の未追跡行は概ね `? <path>\0` なので 8 MiB ≒ 13万件）。
    `FLW-TSK-117`以前は無制限で成功していた経路であり**可用性の後退**。
    設計値として宣言されておらず、超過時の operator action も無い。
  - **10,000 event／100 MiB 条件の収束が未実測。** chain検査は全eventを読むため、
    journalが大きくなったときの収束時間を測っていない。
- **作業内容**:
  - operation単位のdeadlineを導入し、各childへ**残り時間**を配分する。
    残りが尽きたらchildを起動せず`WorktreeChildTimeoutError`へ閉じる。
  - snapshot観測の出力上限を**専用の設計値**として分離定義し、超過時の
    closed resultと operator action を与える。
  - 10,000 event規模のjournalで`inspect()`の収束を実測しmachine evidenceへ残す。
  - §13.4 を実装へ一致させる。
- **完了条件**:
  - 1 operationが起動する全childの合計が operation deadline を超えないこと。
  - 残り時間が尽きた状態でchildを起動しないこと。
  - snapshot出力上限が設計値として宣言され、超過が closed result になること。
  - 10,000 event条件の収束時間が測定され記録されていること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: 既存のchild単位budgetは残す（二重の網）。read-onlyのprobeは変えない。
