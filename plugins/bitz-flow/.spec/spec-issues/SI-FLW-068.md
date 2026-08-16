---
id: SI-FLW-068
raised_by: FLW-REV-018（RSK-301 / DIN-104 / DIN-103 / RSK-305）
target: quarantine の解除経路と nonce ledger の耐久性
proposed_change_type: modify
status: open
---
- **目的**: quarantine が**一方通行**である状態を解消する。入る経路はできたが、
  そこから出る経路が仕様にしか存在しない。

- **発見した事実**:
  1. **解除経路が実装に無い**（`RSK-301` / `DIN-104`）—
     `FLW-DSN-016` §6 は解除 receipt（reviewer・根拠 digest・旧/新 fencing token・結論・時刻）を
     hash-chain へ追記すると定めるが、`reconcile_steps` / `classify_quarantine` には
     **製品コードからの呼び出し元が1つも無い**。quarantine へ落ちた worktree は
     手作業以外で回復できない。
  2. **`PARTIAL` が恒久 `BLOCKED` の袋小路**（`RSK-305`）—
     nonce を `operation_id` から導出したため、同一入力での再試行は必ず消費済み nonce に
     当たる。設計は「残 step だけの新 plan → 新 operation ID」を要求するが、
     利用者にそこへ至る導線が無い。
  3. **nonce ledger の耐久性が3レビュー連続で未解消**（`DIN-103`）—
     directory fsync が無く、temp 名が pid ベースで、`USED_PENDING` の回収機構が無い。
     receipt log 側とは耐久性が非対称であり、**単回性の担保が crash に耐えない**。
     これは出口条件2（repo 外 root の**単回** capability 承認）の根拠に直結する。

- **提案する修正**:
  - 解除 receipt を書く経路を実装し、`classify_quarantine` の4区分を実際に駆動する
  - `PARTIAL` の result に「残 step の新 plan をどう作るか」を `required_human_input` で示す
  - nonce ledger に directory fsync・衝突しない temp 名・`USED_PENDING` 回収を入れる

- **対象ファイル**: `flowlib/worktree_runtime.py`、`flowlib/worktree_cleanup.py`、
  `flowlib/worktree_capability.py`、`flowlib/cli.py`、`tests/test_flow_m2_runtime.py`

- **確認観点**: crash 相当（プロセス kill）後に単回性が保たれること。
  解除区分の4種すべてが実経路から到達可能であること。

- **影響推定・ロールバック**: 出荷面は M0 read-only のままで利用者影響は無い。

- **依存**: 出口条件2の判定に直結する。
