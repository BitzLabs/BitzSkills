---
description: ScalarDB two-phase commit transaction rules — applies when writing Java code that uses TwoPhaseCommitTransactionManager
globs:
  - "**/*.java"
---

# ScalarDB Two-Phase Commit (二相コミット) ルール

## Protocol Order

Two-Phase Commitプロトコルは以下の順序に従わなければならない（MUST）：

```
Coordinator: begin() → CRUD → prepare() → validate() → commit()
Participant: join(txId) → CRUD → (wait) → prepare() → validate() → commit()
```

## Coordinator vs Participant

- **Coordinator (コーディネーター)** は`begin()`または`start()`を呼び出し — トランザクションを開始する
- **Participant (参加者)** は`join(txId)`を呼び出し — IDによって既存のトランザクションに参加する
- **Resume (再開)**（`resume(txId)`） — prepare/validate/commitのために既存のトランザクションに再接続する

## All Participants Must Prepare

もし任意のprepareが失敗した場合、すべてのParticipantはロールバックしなければならない（MUST）：

```java
try {
    tx1.prepare();
    tx2.prepare();
} catch (PreparationException e) {
    tx1.rollback();
    tx2.rollback();
    throw e;
}
```

## Commit Is Best-Effort

もし任意のcommitが成功した場合、トランザクションはコミットされたと見なされる。他のcommitは成功するはずだが、厳密には必須ではない：

```java
tx1.commit();
tx2.commit(); // Should succeed; if it fails, the data will eventually be reconciled
```

## Rollback ALL on Failure

(`UnknownTransactionStatusException`を除く)任意の例外発生時、すべてのParticipantをロールバックする：

```java
} catch (TransactionException e) {
    rollbackAll(tx1, tx2, tx3);
    throw e;
}

private void rollbackAll(TwoPhaseCommitTransaction... txs) {
    for (TwoPhaseCommitTransaction tx : txs) {
        if (tx != null) {
            try { tx.rollback(); } catch (RollbackException e) { /* log */ }
        }
    }
}
```

## Validate Is Conditional

`validate()`は両方の条件が真である場合のみ必須である：
- `scalar.db.consensus_commit.isolation_level=SERIALIZABLE`
- `scalar.db.consensus_commit.serializable_strategy=EXTRA_READ`

この組み合わせを使用しない場合、`validate()`はスキップできる。

## Don't Reuse Transaction IDs

失敗したTwo-Phase Commitトランザクションを再試行する場合、新しいトランザクションIDを使用する（`begin(oldTxId)`ではなく、再度`begin()`を呼び出す）。

## Group Commit Incompatibility

グループコミット（`scalar.db.consensus_commit.coordinator.group_commit.enabled=true`）はTwo-Phase Commitインターフェースと一緒に使用することはできない（CANNOT）。

## Request Routing

Two-Phase Commitトランザクション内のすべての操作は、同じScalarDBクラスタノードにルーティングされなければならない（MUST）：
- 同じ接続でgRPCを使用する（自動）
- L7ロードバランサを使用する場合：セッションアフィニティを使用する
- `direct-kubernetes`モードを使用する場合：コンシステントハッシュにより自動的に処理される

## Microservice Pattern

gRPCを用いたマイクロサービスアーキテクチャにおいて：
1. Coordinatorは`begin()`を呼び出し、`txId`を取得する
2. CoordinatorはgRPCを介してParticipantに`txId`を送信する
3. 各Participantは`join(txId)`を呼び出し、CRUDを実行し、戻る
4. Coordinatorは自身に対して`prepare()`を呼び出し、次にParticipantに`prepare()`するように指示する
5. Coordinatorは自身に対して`validate()`を呼び出し、次にParticipantに`validate()`するように指示する
6. Coordinatorは自身に対して`commit()`を呼び出し、次にParticipantに`commit()`するように指示する
7. 任意のステップでの失敗時、Coordinatorはすべてに`rollback()`するように指示する

Participantは以下に対するgRPCエンドポイントを公開する：`prepare(txId)`、`validate(txId)`、`commit(txId)`、`rollback(txId)`。
これらの各エンドポイントは`resume(txId)`を呼び出し、その後対応する操作を呼び出す。

## JDBC/SQL Two-Phase Commit

JDBC/SQLインターフェースを使用する場合、Two-Phase CommitはJavaのメソッド呼び出しの代わりにSQLのトランザクション制御文を介して管理される。

### SQL 2PC Statements

```sql
BEGIN;                -- or START TRANSACTION;
-- SQL operations (SELECT, INSERT, UPDATE, DELETE)
PREPARE;              -- Prepare the transaction
VALIDATE;             -- Only if SERIALIZABLE + EXTRA_READ
COMMIT;               -- Final commit
-- On failure:
ROLLBACK;             -- or ABORT;
```

### JDBC 2PC Java Code Pattern

```java
try (Connection conn = getConnection()) {
    conn.setAutoCommit(false);
    try {
        // SQL operations via PreparedStatement
        try (PreparedStatement ps = conn.prepareStatement("INSERT INTO ...")) {
            ps.executeUpdate();
        }

        // 2PC protocol via SQL statements
        try (Statement stmt = conn.createStatement()) {
            stmt.execute("PREPARE");
        }
        try (Statement stmt = conn.createStatement()) {
            stmt.execute("VALIDATE"); // Only if SERIALIZABLE + EXTRA_READ
        }

        conn.commit(); // Final commit
    } catch (SQLException e) {
        if (e.getErrorCode() == 301) {
            // UnknownTransactionStatusException — do NOT rollback
            logger.error("Unknown transaction status in 2PC", e);
        } else {
            conn.rollback();
            throw e;
        }
    }
}
```

### CRUD 2PC vs JDBC 2PC Mapping

| CRUD 2PC | JDBC 2PC |
|----------|----------|
| `manager.begin()` | `conn.setAutoCommit(false)` (暗黙的なbegin) |
| `tx.prepare()` | `stmt.execute("PREPARE")` |
| `tx.validate()` | `stmt.execute("VALIDATE")` |
| `tx.commit()` | `conn.commit()` |
| `tx.rollback()` | `conn.rollback()` |
| `tx.getId()` | 接続によって内部的に管理される |
| `manager.join(txId)` | SQLセッション経由（接続ベース） |

### JDBC 2PC Limitations

- トランザクションIDは接続によって内部的に管理される — `tx.getId()`のように直接アクセスすることはできない
- マイクロサービス間のParticipantの調整には、依然としてRPCメカニズム（gRPC、REST）が必要である
- Two-Phase Commitトランザクション内のすべてのステートメントは、同じScalarDBクラスタノードにルーティングされなければならない（MUST）（L7ロードバランサでセッションアフィニティを使用する）
