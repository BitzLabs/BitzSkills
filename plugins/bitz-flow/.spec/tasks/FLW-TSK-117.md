---
implements: FLW-NFR-014
depends_on: [FLW-TSK-116]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,tests/test_flow_m2_liveness.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### Git childへ有限timeoutとprocess supervisionを結線する

`SI-FLW-086`（`FLW-REV-027:SYN-003` P1）。`FLW-DSN-017` §13.4が記録するとおり、
`process.py`は`TimeoutBudget`・SIGTERM/SIGKILL・2.0秒grace・8 MiB出力上限・
Windows job objectをすべて実装済みだが、**worktree経路はこれを一切使っていない**。

- **実測した欠陥**:
  - `worktree_runtime.py`のsubprocess呼び出し（`RepositoryObserver.run`、`_git`、
    `MutationCoordinator.run_git`）はいずれも素の`subprocess.run`で`timeout=`を持たない。
    hangしたGit childは**無期限にブロックする**。
  - `--timeout-seconds`はM0 read operationへは渡るが、worktree経路へは渡らない。
  - `ed25519_verifier`が無制限のopenssl childを起動するが、**呼出元は0件**の死コードである。
- **作業内容**:
  - 3つのGit呼び出しを`process.run()`へ置換し、read/write共通の有限budgetを適用する。
    terminate/kill/wait・出力上限・grace は`process.py`の既定に従う。
  - `--timeout-seconds`をworktree経路の全childへ伝播させる。
  - 終了を証明できないwriteは緊急receiptを保持して`INDETERMINATE`へ閉じる
    （`FLW-DSN-017` §13.2の「終了状態を証明できないGit child」に一致させる）。
    `QUARANTINED`（再観測が予定postconditionと不一致）と混同しない。
  - 死コード`ed25519_verifier`を除去する（無制限child かつ 呼出元0件）。
- **完了条件**:
  - `worktree_runtime.py`に素の`subprocess.run`が0件であること（機械検査）。
  - hangするchildが有限時間でterminal resultへ収束し、例外にも無期限lockにもならないこと。
  - 出力上限超過でchildを終了させclosed resultを返すこと。
  - writeのtimeoutが`INDETERMINATE`になり、緊急receiptが保持されること。
  - `FLW-DSN-017` §13.4の乖離記述を実態へ更新すること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: `FLW-TSK-116`の後。10,000 event/100 MiB規模の負荷testは
  `SI-FLW-090`の証跡整備とあわせて別途行う。
