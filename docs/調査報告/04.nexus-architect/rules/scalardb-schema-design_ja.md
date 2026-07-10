---
description: ScalarDB schema design rules — applies when writing or reviewing ScalarDB schema files (JSON or SQL)
globs:
  - "**/schema.json"
  - "**/schema.sql"
  - "**/*schema*.json"
  - "**/*schema*.sql"
---

# ScalarDB Schema Design Rules

## Transaction Flag

ACID guarantees (ACID保証) を必要とするテーブルには、`"transaction": true`を設定する。これはデフォルトであるが、明示的であるべきだ：

```json
{
  "ns.table": {
    "transaction": true,
    "partition-key": ["id"],
    "columns": { "id": "INT", "name": "TEXT" }
  }
}
```

同一トランザクション内でトランザクショナルなテーブルと非トランザクショナルなテーブルを混在させることはサポートされていない。

## Partition Key Design

- **Even distribution**: データを均等に distribute (分散) するキーを選択する
- **Avoid hot partitions**: 大半のトラフィックを受ける単一の partition key (パーティションキー) の値は bottlenecks (ボトルネック) を引き起こす
- **Common access patterns**: partition key は最も一般的なクエリパターンと一致するべきである
- **Avoid monotonically increasing values**: 単調増加する値（タイムスタンプ、オートインクリメントIDなど）を単独の partition key として使用することは避ける

Good:
```json
"partition-key": ["customer_id"]    // distributes by customer
```

Bad:
```json
"partition-key": ["created_at"]     // hot partition at current time
```

## Clustering Key Design

- パーティション内の sort order (ソート順) を決定する
- 効率的な range queries (レンジクエリ) を可能にする
- `ASC`または`DESC`サフィックスで方向を指定する

```json
"clustering-key": ["timestamp DESC", "item_id ASC"]
```

## No JOIN in CRUD API

CRUD APIはJOINをサポートしていない。単一テーブルへのアクセスを前提としたスキーマを設計する：

- **Denormalize**: JOINを避けるために、テーブル間でデータを denormalize (非正規化) して複製する
- **Application-level joins**: application-level joins (アプリケーションレベルの結合) として、同一トランザクション内で複数のテーブルから読み取る
- **Design around access patterns**: アクセスパターンを中心とした設計を行い、各テーブルが特定のクエリパターンに対応するようにする

JOINが必要な場合は、SQL/JDBCインターフェース（Clusterモードのみ）を使用すること。

## Secondary Index Guidelines

- キー以外のカラムによる時折の lookups (ルックアップ) に使用する
- 各 index (インデックス) は書き込みのオーバーヘッドを増加させる
- 一部のバックエンド（Cassandraなど）では、 cardinality (カーディナリティ) の高いカラムのインデックス付けを避ける
- 代替案: インデックス対象のカラムを partition key とする別のテーブルを作成する

```json
"secondary-index": ["order_id"]     // enables Get by order_id
```

## Supported Data Types

`BOOLEAN`, `INT`, `BIGINT`, `FLOAT`, `DOUBLE`, `TEXT`, `BLOB`, `DATE`, `TIME`, `TIMESTAMP`, `TIMESTAMPTZ`

データに適合する最も狭い型を選択する。

## SQL Reserved Words

SQLのDDLを使用する場合、カラム名としての reserved words (予約語) は引用符で囲む：

```sql
CREATE TABLE ns.tbl (
  id INT PRIMARY KEY,
  "timestamp" BIGINT,    -- quoted
  "order" TEXT           -- quoted
);
```

## Schema JSON Required Fields

すべてのテーブル定義は以下を必ず持たなければならない：
- `partition-key` (カラム名の配列)
- `columns` (カラム名から型へのマッピングオブジェクト)

オプション：
- `transaction` (デフォルト `true`)
- `clustering-key` (オプションでASC/DESCを伴う配列)
- `secondary-index` (カラム名の配列)

## Coordinator Tables

coordinator tables (コーディネーターテーブル) は、トランザクション操作に必須である。以下を使用して作成する：
- Schema Loader: `--coordinator` フラグ
- SQL: `CREATE COORDINATOR TABLES IF NOT EXIST`
