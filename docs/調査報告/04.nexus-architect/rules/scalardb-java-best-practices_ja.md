---
description: ScalarDBアプリケーションのJavaベストプラクティス — ScalarDBを使用するJavaコードを記述する際に適用される
globs:
  - "**/*.java"
---

# ScalarDBのJavaベストプラクティス

## TransactionManagerにtry-with-resourcesを使用する

`DistributedTransactionManager`と`TwoPhaseCommitTransactionManager`は`AutoCloseable`を実装している。

```java
try (DistributedTransactionManager manager = factory.getTransactionManager()) {
    // use manager
}
```

または、`Closeable`を実装したサービスクラスでライフサイクルを明示的に管理する。

```java
public class MyService implements Closeable {
    private final DistributedTransactionManager manager;

    public MyService(String configFile) throws TransactionException {
        TransactionFactory factory = TransactionFactory.create(configFile);
        manager = factory.getTransactionManager();
    }

    @Override
    public void close() throws IOException {
        manager.close();
    }
}
```

## TransactionFactoryは一度だけ初期化する

`TransactionFactory.create()`はコストが高い。一度だけ作成して再利用する。

```java
// CORRECT — create once:
TransactionFactory factory = TransactionFactory.create("database.properties");
DistributedTransactionManager manager = factory.getTransactionManager();

// WRONG — creating factory per operation:
public void doSomething() {
    TransactionFactory factory = TransactionFactory.create("database.properties"); // expensive!
    // ...
}
```

## スレッド間でトランザクションオブジェクトを共有しない

`DistributedTransaction`と`TwoPhaseCommitTransaction`は`@NotThreadSafe`である。各スレッドは独自のトランザクションを使用しなければならない。

```java
// WRONG:
DistributedTransaction tx = manager.begin();
executor.submit(() -> tx.get(...));  // unsafe
executor.submit(() -> tx.insert(...)); // unsafe

// CORRECT:
executor.submit(() -> {
    DistributedTransaction tx = manager.begin();
    tx.get(...);
    tx.commit();
});
```

## トランザクションを短く保つ

実行時間の長いトランザクションは、競合の確率とリソース使用量を増加させる。
- トランザクションを開始する前にすべての計算を行う
- トランザクション内にはデータベース操作のみを含める
- トランザクション内での外部APIの呼び出しは避ける

```java
// CORRECT — compute first, then transact:
int newTotal = computeNewTotal(items);
DistributedTransaction tx = manager.begin();
tx.update(...);
tx.commit();

// WRONG — computation inside transaction:
DistributedTransaction tx = manager.begin();
int newTotal = computeNewTotal(items); // slow computation holds transaction open
tx.update(...);
tx.commit();
```

## ロギングにSLF4Jを使用する

ScalarDBは内部でSLF4Jを使用している。一貫性のために同じものを使用する。

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class MyService {
    private static final Logger logger = LoggerFactory.getLogger(MyService.class);

    public void doSomething() {
        logger.info("Processing order: {}", orderId);
    }
}
```

build.gradleにSLF4Jのバインディングを追加する。
```groovy
runtimeOnly 'org.apache.logging.log4j:log4j-slf4j2-impl:2.20.0'
runtimeOnly 'org.apache.logging.log4j:log4j-core:2.20.0'
```

## CLIアプリケーションにpicocliを使用する

ScalarDBのサンプルでは、コマンドライン引数の解析にpicocliを使用している。

```groovy
dependencies {
    implementation 'info.picocli:picocli:4.7.1'
}
```

## オペレーションオブジェクトの再利用を避ける

オペレーションオブジェクト (`Get`、`Scan`、`Insert`など) は`@NotThreadSafe`である。使用するたびに新しいインスタンスを構築する。

```java
// CORRECT — new builder each time:
for (int id : ids) {
    Optional<Result> result = tx.get(
        Get.newBuilder().namespace("ns").table("tbl")
            .partitionKey(Key.ofInt("id", id)).build());
}
```

## Null許容のResult値を処理する

`Result`からのオブジェクト型のゲッターはnullを返す可能性がある。
```java
// Safe pattern:
String name = result.getText("name");
if (name != null) {
    // use name
}

// Or check first:
if (!result.isNull("name")) {
    String name = result.getText("name");
}
```

## 注文/エンティティのIDにUUIDを使用する

```java
String orderId = UUID.randomUUID().toString();
```

ScalarDBは、カスタムトランザクションIDにもUUID v4フォーマットを推奨している。

## JDBC固有のベストプラクティス

### 接続ヘルパーメソッドを使用する

`DriverManager.getConnection()`と`setAutoCommit(false)`をヘルパーに集中させる。

```java
private static final String JDBC_URL = "jdbc:scalardb:scalardb-sql.properties";

private Connection getConnection() throws SQLException {
    Connection conn = DriverManager.getConnection(JDBC_URL);
    conn.setAutoCommit(false);
    return conn;
}
```

### トランザクションごとに新しい接続を取得する

JDBC接続はスレッド間で共有してはならない。トランザクションごとに新しい接続を取得する。

```java
// CORRECT — one connection per transaction:
public void doWork() throws SQLException {
    try (Connection conn = getConnection()) {
        // ... operations ...
        conn.commit();
    }
}

// WRONG — sharing a connection across threads:
private Connection sharedConn; // unsafe for concurrent use
```

### すべてのJDBCリソースを閉じる

Connection、PreparedStatement、ResultSetには常にtry-with-resourcesを使用する。

```java
try (Connection conn = getConnection()) {
    try (PreparedStatement ps = conn.prepareStatement(sql)) {
        try (ResultSet rs = ps.executeQuery()) {
            while (rs.next()) { /* process */ }
        }
    }
    conn.commit();
}
```

### PreparedStatementを使用し、文字列連結は絶対に行わない

SQLインジェクションを防ぐために、常にパラメータ化されたクエリを使用する。

```java
// CORRECT:
PreparedStatement ps = conn.prepareStatement("SELECT * FROM ns.tbl WHERE id = ?");
ps.setInt(1, id);

// WRONG — SQL injection risk:
Statement stmt = conn.createStatement();
stmt.executeQuery("SELECT * FROM ns.tbl WHERE id = " + id);
```

### JDBCトランザクションを短く保つ

CRUD APIと同様に、トランザクションの外部で計算を行う。

### JDBCドライバークラス名

ScalarDBのJDBCドライバーはSPI経由で自動的にロードされる。`Class.forName()`を呼び出す必要はない。

```java
// NOT needed — driver is loaded automatically:
// Class.forName("com.scalar.db.sql.jdbc.SqlJdbcDriver");

// Just use DriverManager directly:
Connection conn = DriverManager.getConnection("jdbc:scalardb:config.properties");
```
