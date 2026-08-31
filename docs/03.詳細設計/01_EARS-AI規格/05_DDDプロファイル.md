# EARS-AI DDD Profile（将来候補）

## 1. 状態

- 状態: Deferred Draft
- Core 1.0: 対象外
- 導入条件: DDDを採用する複数の実プロジェクトでトレース上の便益が確認されること

## 2. 目的

CoreへDDD概念を持ち込まず、必要なプロジェクトだけがBounded Context、Aggregate、Entity、
Value Objectなどを規範文へ関連付ける拡張点を予約する。

## 3. 予約語彙

| タグ | 用途 |
|---|---|
| `ddd:BOUNDED_CONTEXT` | 境界づけられたコンテキスト |
| `ddd:AGGREGATE_ROOT` | 集約ルート |
| `ddd:ENTITY` | Entity |
| `ddd:VALUE_OBJECT` | Value Object |
| `ddd:DOMAIN_EVENT` | Domain Event |

## 4. 制約

- DDD Profileは明示的に有効化された場合だけ検査する。
- 無効時にDDD成果物やタグを要求しない。
- タグからコード構造を自動生成・強制することをCoreの保証にしない。
- Profileの導入が`bitz check`の通常性能予算を超える場合、別コマンドまたは明示オプションにする。

## 5. 例

```markdown
- [REQ-001:INV-01] [ddd:BOUNDED_CONTEXT=Ordering] [ddd:AGGREGATE_ROOT=Order] [ACTOR:Order] [ALWAYS] [MUST] [CONSTRAINT] 確定済み注文の合計金額を負数にしない。
```
