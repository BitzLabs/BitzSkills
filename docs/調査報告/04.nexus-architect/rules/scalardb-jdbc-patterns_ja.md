---
description: ScalarDB JDBC/SQL usage rules — applies when writing Java code that uses ScalarDB SQL JDBC driver
globs:
  - "**/*.java"
---

# ScalarDB JDBC/SQL Rules

## Always setAutoCommit(false)

ScalarDBは明示的な transaction management (トランザクション管理) を必要とする：

```java
Connection conn = DriverManager.getConnection("jdbc:scalardb:config.properties");
conn.setAutoCommit(false); // CRITICAL
```

## Always Commit Even for Read-Only

```java
try (Connection conn = getConnection()) {
    try {
        // Read-only query
        try (PreparedStatement ps = conn.prepareStatement("SELECT * FROM ns.tbl WHERE id = ?")) {
            ps.setInt(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                // process results
            }
        }
        conn.commit(); // REQUIRED even for reads
    } catch (Exception e) {
        conn.rollback();
        throw e;
    }
}
```

## Always Rollback in Catch Blocks

```java
try {
    // operations
    conn.commit();
} catch (Exception e) {
    conn.rollback();
    throw e;
}
```

## Use PreparedStatement with Parameters

SQL文字列に値を連結してはならない：

```java
// CORRECT:
PreparedStatement ps = conn.prepareStatement("SELECT * FROM ns.tbl WHERE id = ?");
ps.setInt(1, customerId);

// WRONG — SQL injection risk:
Statement stmt = conn.createStatement();
stmt.executeQuery("SELECT * FROM ns.tbl WHERE id = " + customerId);
```

## Use try-with-resources

Connection、PreparedStatement、およびResultSetは常に close (クローズ) すること：

```java
try (Connection conn = getConnection()) {
    try (PreparedStatement ps = conn.prepareStatement(sql)) {
        ps.setInt(1, id);
        try (ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                // process
            }
        }
    }
    conn.commit();
}
```

## JDBC URL Format

```
jdbc:scalardb:<config-file-path>[?property=value&...]
```

例：
- `jdbc:scalardb:scalardb-sql.properties`
- `jdbc:scalardb:/path/to/config.properties`
- `jdbc:scalardb:?scalar.db.sql.connection_mode=cluster&scalar.db.sql.cluster_mode.contact_points=indirect:localhost`

## Quote Reserved Words

カラム名として使用されるSQLの reserved words (予約語) は引用符で囲む必要がある：

```sql
-- CORRECT:
INSERT INTO ns.orders (customer_id, "timestamp", order_id) VALUES (?, ?, ?)

-- WRONG — timestamp is a reserved word:
INSERT INTO ns.orders (customer_id, timestamp, order_id) VALUES (?, ?, ?)
```

ScalarDBのスキーマにおける一般的な reserved words： `timestamp`, `order`, `key`, `index`, `table`, `column`

## Use namespace.table Format

テーブル名は常に namespace (名前空間) で修飾すること：

```sql
SELECT * FROM sample.customers WHERE customer_id = ?
INSERT INTO sample.orders (customer_id, "timestamp") VALUES (?, ?)
```

## JDBC Data Type Mapping

| ScalarDB | Java setter | Java getter |
|----------|-------------|-------------|
| BOOLEAN | `setBoolean()` | `getBoolean()` |
| INT | `setInt()` | `getInt()` |
| BIGINT | `setLong()` | `getLong()` |
| FLOAT | `setFloat()` | `getFloat()` |
| DOUBLE | `setDouble()` | `getDouble()` |
| TEXT | `setString()` | `getString()` |
| BLOB | `setBytes()` | `getBytes()` |
| DATE | `setObject(LocalDate)` | `getObject(LocalDate.class)` |
| TIME | `setObject(LocalTime)` | `getObject(LocalTime.class)` |
| TIMESTAMP | `setObject(LocalDateTime)` | `getObject(LocalDateTime.class)` |
| TIMESTAMPTZ | `setObject(Instant)` | `getObject(Instant.class)` |

**Important**: DATE、TIME、TIMESTAMP、TIMESTAMPTZについては、レガシーなJDBCメソッド（`setDate()`、`setTimestamp()`、`getDate()`、`getTimestamp()`）ではなく、必ず`setObject()` / `getObject()`を使用しなければならない。

## JDBC Exception Handling

すべてのScalarDB SQL例外はエラーコードとともに`java.sql.SQLException`にラップされる：

```java
try {
    conn.commit();
} catch (SQLException e) {
    if (e.getErrorCode() == 301) {
        // UnknownTransactionStatusException — do NOT rollback
        // Verify if committed, retry only if not
    } else {
        conn.rollback();
        // Check e.getCause() for TransactionRetryableException (safe to retry)
        // Other causes may be non-transient — limit retries
    }
}
```

## JOIN Syntax

ScalarDB SQLはINNER、LEFT OUTER、およびRIGHT OUTER JOINをサポートする（Clusterモードのみ）：

```sql
-- INNER JOIN
SELECT o.order_id, c.name
FROM ns.orders o
INNER JOIN ns.customers c ON o.customer_id = c.customer_id
WHERE o.customer_id = ?

-- LEFT OUTER JOIN
SELECT c.name, o.order_id
FROM ns.customers c
LEFT JOIN ns.orders o ON c.customer_id = o.customer_id

-- RIGHT OUTER JOIN (must be the first join)
SELECT c.name, o.order_id
FROM ns.orders o
RIGHT JOIN ns.customers c ON o.customer_id = c.customer_id
```

**JOIN constraints**: JOINの predicates (述語) には、結合されるテーブルのすべての primary key (プライマリキー) カラム、または secondary index (セカンダリインデックス) カラムのいずれかが含まれていなければならない。FULL OUTER JOINはサポートされていない。

## Aggregate Functions

サポートされている aggregate functions (集約関数)： `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`

```sql
SELECT COUNT(*) FROM ns.orders WHERE customer_id = ?
SELECT customer_id, SUM(amount) FROM ns.orders GROUP BY customer_id
SELECT customer_id, AVG(amount) FROM ns.orders GROUP BY customer_id HAVING AVG(amount) > 100
```

`*`をサポートするのは`COUNT`のみである。それ以外のすべての aggregate functions ではカラム名が必要である。

## SQL Limitations

- **No DISTINCT** keyword
- **No subqueries**
- **No CTEs** (Common Table Expressions / WITH句)
- **No window functions**
- **No FULL OUTER JOIN**
- **No UNION / INTERSECT / EXCEPT**
- JOINの predicates は、primary key または secondary index のカラムを参照しなければならない
- WHERE句は、disjunctive normal form (選言標準形: ANDのOR) または conjunctive normal form (連言標準形: ORのAND) のいずれかである必要がある

## 2PC via SQL Statements

JDBCでの Two-Phase Commit (二相コミット) には、SQLのトランザクション制御ステートメントを使用する：

```java
try (Statement stmt = conn.createStatement()) {
    stmt.execute("PREPARE");
}
try (Statement stmt = conn.createStatement()) {
    stmt.execute("VALIDATE"); // Only if SERIALIZABLE + EXTRA_READ
}
conn.commit();
```

詳細については、2PCパターンのルールを参照すること。
