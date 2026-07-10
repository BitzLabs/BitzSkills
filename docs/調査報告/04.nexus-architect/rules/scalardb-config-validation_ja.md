---
description: ScalarDB設定検証ルール — ScalarDBのプロパティファイルを記述またはレビューする際に適用される
globs:
  - "**/*.properties"
  - "**/database.properties"
  - "**/scalardb*.properties"
---

# ScalarDB 設定検証ルール

## ストレージタイプ別の必須プロパティ

### JDBC（MySQL、PostgreSQL、Oracle、SQL Server）

必須:
- `scalar.db.storage=jdbc`
- `scalar.db.contact_points=<JDBC_URL>`
- `scalar.db.username=<user>`
- `scalar.db.password=<password>`

### Cassandra

必須:
- `scalar.db.storage=cassandra`
- `scalar.db.contact_points=<host>`
- `scalar.db.username=<user>`
- `scalar.db.password=<password>`

### DynamoDB

必須:
- `scalar.db.storage=dynamo`
- `scalar.db.contact_points=<region>`
- `scalar.db.username=<AWS_ACCESS_KEY_ID>`
- `scalar.db.password=<AWS_SECRET_ACCESS_KEY>`

DynamoDB Localの場合、追加で以下が必要:
- `scalar.db.dynamo.endpoint_override=http://localhost:8000`

### Cosmos DB

必須:
- `scalar.db.storage=cosmos`
- `scalar.db.contact_points=<COSMOS_DB_URI>`
- `scalar.db.password=<COSMOS_DB_KEY>`

## 有効な値

### scalar.db.storage

有効な値: `jdbc`、`cassandra`、`dynamo`、`cosmos`、`multi-storage`

### scalar.db.transaction_manager

有効な値: `consensus-commit`（デフォルト）、`single-crud-operation`、`cluster`

### scalar.db.consensus_commit.isolation_level

有効な値: `SNAPSHOT`（デフォルト）、`SERIALIZABLE`、`READ_COMMITTED`

## クラスタモードの設定

### CRUD API（Primitive Interface）

必須:
- `scalar.db.transaction_manager=cluster`
- `scalar.db.contact_points=<mode>:<host>`

### SQL/JDBC API

必須:
- `scalar.db.sql.connection_mode=cluster`
- `scalar.db.sql.cluster_mode.contact_points=<mode>:<host>`

## コンタクトポイントの形式

コンタクトポイントは接続モードのプレフィックスを必ず付けなければならない:

| モード | 形式 | 例 |
|------|--------|---------|
| 間接的（ロードバランサ） | `indirect:<host>` | `indirect:lb.example.com` |
| 直接 Kubernetes | `direct-kubernetes:<ns>/<ep>` | `direct-kubernetes:scalardb/scalardb-cluster` |
| 直接 Kubernetes（デフォルトの名前空間） | `direct-kubernetes:<ep>` | `direct-kubernetes:scalardb-cluster` |

よくある間違い: モードのプレフィックスを省略すること。

```properties
# CORRECT:
scalar.db.contact_points=indirect:localhost

# WRONG — missing mode prefix:
scalar.db.contact_points=localhost
```

## クロスパーティションスキャン

`Scan.newBuilder().all()` を使用するには明示的に有効化する必要がある:

```properties
scalar.db.cross_partition_scan.enabled=true
# Optional:
scalar.db.cross_partition_scan.filtering.enabled=true
scalar.db.cross_partition_scan.ordering.enabled=true
```

## マルチストレージの設定

必須:
- `scalar.db.storage=multi-storage`
- `scalar.db.multi_storage.storages=<name1>,<name2>`
- `scalar.db.multi_storage.default_storage=<name>`
- `scalar.db.multi_storage.namespace_mapping=<ns1>:<name1>,<ns2>:<name2>`
- ストレージごとのプロパティ: `scalar.db.multi_storage.storages.<name>.<property>`

## SQL認証プロパティ

SQL/JDBCクラスタモードでは、SQL固有の認証プロパティを使用すること:
- `scalar.db.sql.cluster_mode.username`（`scalar.db.username`ではない）
- `scalar.db.sql.cluster_mode.password`（`scalar.db.password`ではない）

## プレースホルダーのサポート

プロパティは環境変数とシステムプロパティをサポートしている:
```properties
scalar.db.username=${env:DB_USER:-defaultUser}
scalar.db.password=${sys:db.password:-defaultPass}
```
