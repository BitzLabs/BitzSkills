---
description: ScalarDBの例外処理ルール — ScalarDBのトランザクションAPIを使用するJavaコードを記述またはレビューする際に適用される
globs:
  - "**/*.java"
---

# ScalarDBの例外処理ルール

## catchの順序 (重要)

特定の競合例外は、常にその親クラスよりも前にcatchしなければならない。親を先にcatchすると、競合のcatchブロックに到達できなくなる。

```java
// CORRECT:
catch (CrudConflictException e) { ... }   // specific first
catch (CrudException e) { ... }           // parent second

// WRONG — CrudConflictException is unreachable:
catch (CrudException e) { ... }
catch (CrudConflictException e) { ... }   // NEVER REACHED
```

これはすべての例外のペアに適用される：
- `CrudException`の前に`CrudConflictException`
- `CommitException`の前に`CommitConflictException`
- `PreparationException`の前に`PreparationConflictException`
- `ValidationException`の前に`ValidationConflictException`

## catchブロックでのロールバック/アボート

catchブロックでは、必ずトランザクションをアボート/ロールバックしなければならない。

```java
} catch (TransactionException e) {
    if (transaction != null) {
        try { transaction.rollback(); } catch (RollbackException ex) { /* log */ }
    }
}
```

例外: `UnknownTransactionStatusException`の場合はロールバックしてはならない。ステータスが不明であり、ロールバックが干渉する可能性があるためである。

## UnknownTransactionStatusException

これは正しく処理すべき最も重要な例外である：
- コミットは成功したかもしれないし、失敗したかもしれない — どちらかは不明である
- 盲目的にリトライしてはならない — 重複データを作成する可能性がある
- 調査のためにトランザクションIDをログに記録する
- これを安全に処理するために、冪等性のパターンを使用する

## 常にコミットする (読み取り専用でも)

読み取り専用のトランザクションでも必ず`commit()`を呼び出さなければならない。コミットを忘れるとトランザクションが開いたままになり、リソースを無駄にする。

## トランザクションIDのログ記録

すべてのScalarDBの例外は`getTransactionId()`を提供する。デバッグのために必ずログに記録する。

```java
} catch (TransactionException e) {
    logger.error("Transaction failed. txId={}", e.getTransactionId().orElse("unknown"), e);
}
```

## 競合例外はリトライ可能

`*ConflictException`タイプは一時的なものであるため、`begin()`からトランザクション全体をリトライする：
- `CrudConflictException`
- `CommitConflictException`
- `PreparationConflictException`
- `ValidationConflictException`

## UnsatisfiedConditionExceptionはリトライ不可

これは、変更条件 (例: `updateIfExists()`) が満たされなかったことを意味する。これはアプリケーションロジックの問題であり、一時的なエラーではない。

## JDBC/SQLの例外処理

ScalarDBのJDBCドライバーを使用する場合、すべてのScalarDB SQL例外は`java.sql.SQLException`にラップされる。JDBCドライバーは、エラーコードと例外の原因を使用して例外タイプを区別する。

### エラーコード301: UnknownTransactionStatusException

最も重要なJDBCエラーコードである。`e.getErrorCode() == 301`の場合：
- ロールバックしてはならない — トランザクションのステータスは不明である
- 盲目的にリトライしてはならない — トランザクションはすでにコミットされている可能性がある
- トランザクションがコミットされたかどうかを手動で確認し、コミットされていない場合にのみリトライしなければならない

### リトライ可能なSQLExceptionとリトライ不可なSQLException

エラーコード301以外のSQLExceptionの場合：
- 常に最初にロールバックする
- `e.getCause()`が`TransactionRetryableException`であるかどうかを確認する — そうであれば、トランザクションをリトライする
- その他の原因の場合、エラーは一時的ではない可能性がある — 最大回数を制限してリトライする

### 正しいJDBC例外処理パターン

```java
connection.setAutoCommit(false);
try {
    // Execute statements (SELECT/INSERT/UPDATE/DELETE)
    connection.commit();
} catch (SQLException e) {
    if (e.getErrorCode() == 301) {
        // UnknownTransactionStatusException — do NOT rollback
        // Must verify if the transaction committed, then retry if it did not
        logger.error("Unknown transaction status", e);
    } else {
        connection.rollback();
        // The cause can be TransactionRetryableException or other exceptions.
        // For TransactionRetryableException, you can basically retry.
        // For other exceptions, the cause may be non-transient — limit retries.
    }
}
```

### SQL APIの例外階層

ScalarDB SQL API (非JDBC) は、`com.scalar.db.sql.exception`に独自の例外階層を持っている：
- `SqlException` — 基本例外クラス
- `TransactionRetryableException` — リトライ可能。トランザクション全体を安全にリトライできる
- `UnknownTransactionStatusException` — コミットステータスが不明。盲目的にリトライしてはならない

SQL APIを直接 ( `SqlSession`経由で ) 使用する場合：
```java
try {
    sqlSession.begin();
    // Execute statements
    sqlSession.commit();
} catch (UnknownTransactionStatusException e) {
    // Do NOT rollback — status unknown; verify and retry if needed
} catch (SqlException e) {
    sqlSession.rollback();
    // Retry with limits
}
```

### 読み取り専用のJDBCトランザクションでも常にコミットする

CRUD APIと同様に、読み取り専用のJDBCトランザクションでも必ず`conn.commit()`を呼び出さなければならない。

### JDBCのcatchブロックでは常にロールバックする

catchブロックでは常に`conn.rollback()`を呼び出さなければならない (エラーコード301を除く)。
