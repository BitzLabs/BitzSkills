---
description: ScalarDB CRUD API使用ルール — ScalarDBのCRUD操作を使用するJavaコードを書く際に適用される
globs:
  - "**/*.java"
---

# ScalarDB CRUD API ルール

## 常にビルダーパターンを使用すること

すべての操作はビルダーパターンを使用しなければならない:

```java
Get.newBuilder().namespace("ns").table("tbl").partitionKey(key).build();
Scan.newBuilder().namespace("ns").table("tbl").partitionKey(key).build();
Insert.newBuilder().namespace("ns").table("tbl").partitionKey(key).build();
```

`new Get(key)` のような非推奨のコンストラクタを使用してはならない。

## 常に名前空間とテーブルを指定すること

すべての操作において `.namespace()` と `.table()` を明示的に設定しなければならない:

```java
// CORRECT:
Get.newBuilder()
    .namespace("sample")
    .table("customers")
    .partitionKey(Key.ofInt("customer_id", 1))
    .build();

// WRONG — missing namespace/table:
Get.newBuilder()
    .partitionKey(Key.ofInt("customer_id", 1))
    .build();
```

## Putは非推奨 — Insert、Upsert、またはUpdateを使用すること

ScalarDB 3.13.0以降、`Put` は非推奨である。以下を使用すること:
- `Insert` — 挿入のみ。レコードが存在する場合は競合をスローする
- `Upsert` — 挿入または更新（条件なし）
- `Update` — 更新のみ。レコードが存在しない場合は何もしない

```java
// DEPRECATED:
transaction.put(Put.newBuilder()...build());

// USE INSTEAD:
transaction.insert(Insert.newBuilder()...build());
transaction.upsert(Upsert.newBuilder()...build());
transaction.update(Update.newBuilder()...build());
```

## キーの構築

型付きのファクトリメソッドを使用すること:

```java
Key.ofInt("col", 42)
Key.ofText("col", "hello")
Key.ofBigInt("col", 9999L)
Key.ofDouble("col", 3.14)
Key.ofBoolean("col", true)
```

複合キーの場合:

```java
Key.newBuilder()
    .addInt("col1", 1)
    .addText("col2", "hello")
    .build();
```

## Optional<Result>を適切にチェックすること

`get()` は `Optional<Result>` を返す。アクセスする前に常にチェックすること:

```java
Optional<Result> result = transaction.get(get);
if (!result.isPresent()) {
    // Handle missing record
}
String name = result.get().getText("name");
```

## ResultのNull処理

プリミティブのゲッターは、NULLの場合にデフォルト値を返す:
- `getInt()` → 0
- `getBigInt()` → 0L
- `getFloat()` → 0.0f
- `getDouble()` → 0.0
- `getBoolean()` → false

オブジェクトのゲッターはnullを返す:
- `getText()` → null
- `getBlob()` → null

明示的にNULLをチェックするには `isNull("col")` を使用すること。

## 複数の変更にはmutate()を使用すること

非推奨の `put(List)` や `delete(List)` の代わりに、`mutate()` を使用すること:

```java
transaction.mutate(Arrays.asList(insert1, update1, delete1));
```

## クロスパーティションスキャンには設定が必要

`Scan.newBuilder().all()` を使用するには以下が必要である:
```properties
scalar.db.cross_partition_scan.enabled=true
```
