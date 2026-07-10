# ScalarDB コーディングパターン

このファイルは、ScalarDBのコーディングパターンの統合インデックスである。各トピックは、それぞれの専用ルールファイルで詳細にカバーされている。

## ルールファイル

| トピック | ファイル | 読むべきタイミング |
|-------|------|--------------|
| CRUD API操作（Get、Scan、Insert、Upsert、Update、Delete） | @rules/scalardb-crud-patterns.md | CRUD操作を書く時 |
| JDBC/SQL操作（SELECT、INSERT、JOIN、集計） | @rules/scalardb-jdbc-patterns.md | SQLベースの操作を書く時 |
| 例外処理とリトライロジック | @rules/scalardb-exception-handling.md | 例外をキャッチし処理する時 |
| Two-Phase Commit（二相コミット）プロトコル | @rules/scalardb-2pc-patterns.md | サービス間で2PCを実装する時 |
| Javaベストプラクティス（トランザクションライフサイクル、スレッディング、ロギング） | @rules/scalardb-java-best-practices.md | Javaアプリケーションコードを書く時 |
| スキーマ設計（パーティションキー、クラスタリングキー、インデックス） | @rules/scalardb-schema-design.md | テーブルスキーマを設計する時 |
| 設定の検証（ストレージ、クラスタ、コンタクトポイント） | @rules/scalardb-config-validation.md | 設定ファイルを書く時 |

## クイックリファレンス

### トランザクションライフサイクル（CRUD API）

```java
DistributedTransaction tx = manager.begin();
try {
    // CRUD operations
    tx.commit();
} catch (CommitConflictException | CrudConflictException e) {
    tx.rollback();
    // retry
} catch (UnknownTransactionStatusException e) {
    // DO NOT rollback — status unknown
} catch (TransactionException e) {
    tx.rollback();
}
```

### トランザクションライフサイクル（JDBC）

```java
connection.setAutoCommit(false);
try {
    // SQL operations
    connection.commit();
} catch (SQLException e) {
    if (e.getErrorCode() == 301) {
        // UnknownTransactionStatusException — DO NOT rollback
    } else {
        connection.rollback();
    }
}
```

### 主要なルール

- 常に親の `*Exception` の **前** に `*ConflictException` をキャッチすること
- 読み取り専用トランザクションであっても常に `commit()` を呼び出すこと
- `UnknownTransactionStatusException` では決してロールバックしないこと
- ビルダーパターン（`Get.newBuilder()...`）を使用すること — 非推奨のコンストラクタは決して使用しないこと
- `Insert`/`Upsert`/`Update` を使用すること — 非推奨の `Put` は決して使用しないこと
