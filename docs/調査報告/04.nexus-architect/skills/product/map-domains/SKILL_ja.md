---
description: |
  機能とエンティティを境界付けられたコンテキスト（bounded contexts）に抽象化します（DDDの戦略的設計） — Core/Supporting/Generic のドメインマップ、関係性を示すコンテキストマップ、およびユビキタス言語（ubiquitous language） — 将来の機能を吸収できるサイズに設定します。nexus-architect への橋渡しをします。/product:map-domains [--auto] [--lang=ja|en]。
model: opus
user_invocable: true
---

# Domain Map & Bounded Contexts

## Desired Outcome

3つの成果物を作成します：

1. **ドメインマップ（Domain map）** — `reports/03_domain/domain-map.md`: サブドメインを **Core / Supporting / Generic** に分類し、投資のガイダンス（Coreは構築する、Supportingは実用的に、Genericは購入する）を伴います。
2. **境界付けられたコンテキスト（Bounded contexts）** — `reports/03_domain/bounded-contexts.md`（`CTX-` IDs）: 各コンテキスト、それが所有するエンティティ/機能、関係性の**コンテキストマップ（Context Map）**（ACL, Open Host / Published Language, Shared Kernel, Customer/Supplier, Conformist, Partnership）、およびコンテキストごとの大まかな**一貫性のヒント（consistency hint）**（`Strong` / `Eventual` / `TBD`） — これは*ヒント*であり、決定事項ではありません。これはアーキテクト（architect）のプロセスごとのトランザクションの一貫性分類のシードとなり（Handoff を参照）、そこで最終的な ACID / Saga / ローカルトランザクション（Local-Tx）の判定が行われます。
3. **ユビキタス言語（Ubiquitous language）** — `reports/03_domain/ubiquitous-language.md`: コンテキストごとの共有される語彙（すべての `ENT-`/用語がここに表示されます）。

## Invocation

```
/product:map-domains [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--auto` | Optional | ファシリテーションなしで導出します。境界が曖昧な場合は `TBD` になります |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **境界は画面ではなく、ビジネス機能に従う** — そして、将来起こり得る機能を吸収できるサイズに設定します（拡張性）。
- **Generic ではなく Core に投資する。** Generic なサブドメイン（認証、請求）を過剰にエンジニアリングしないこと。腐敗防止層（Anticorruption Layer）で Core を保護します。
- **コンテキスト間の疎結合（Loose coupling）** — 関係性は明示的です（ACL / Published Language）。
- **終了条件（Stop condition）**: すべてのエンティティ/機能がコンテキストに属しており、サブドメインが Core/Supporting/Generic に分類され、コンテキストマップに型付きの関係性があり、ユビキタス言語がすべての用語をカバーしていること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/02_spec/data-model.md` | Required | `/product:define-data-model` | メッセージを出してブロックする — コンテキストはエンティティをグループ化します |
| `reports/02_spec/feature-list.md` | Required | `/product:define-features` | メッセージを出してブロックする — ケーパビリティが境界を定義します |

## Process

1. **コンテキストの読み取り** — データモデル、機能、`work/traceability.json`。
2. **サブドメインの分類（Classify subdomains）** — Core / Supporting / Generic。投資のガイダンスを記録します。`@rules/product/ddd-strategic.md` を適用します。
3. **コンテキストの描画（Draw contexts）** — エンティティ/機能を将来に向けてサイズ調整された `CTX-` の境界付けられたコンテキストにグループ化します。
4. **関係性のマッピング（Map relationships）** — コンテキスト間の各関係性を型付けします（ACL、Published Language など）。
5. **一貫性のヒントのタグ付け（Tag consistency hint）** — 各 `CTX-` について、その操作の性質（お金/在庫/予約の不変条件 → `Strong`。リードモデル、アナリティクス、通知 → `Eventual`。不明 → `TBD`）から大まかな `Strong` / `Eventual` / `TBD` のヒントを、一行の根拠とともにマークします。これはアーキテクトのためのシードであり、拘束力のあるトランザクションの決定事項ではありません。
6. **言語の定義（Define language）** — コンテキストごとのユビキタス言語。
7. **トレーサビリティの追記** — 上流の `ENT-`/`FEAT-` 参照を持つ `CTX-` ノードを `work/traceability.json` に追加します。
8. **記録** — 3つのファイルを書き込みます。決定事項を `work/context.md` に追記します。`TBD` をログに記録します。

## Handoff

`CTX-` 境界付けられたコンテキスト + ユビキタス言語は、アーキテクト（architect）の Bounded Context の入力（`docs/design.md` §1.3）にマッピングされます — これが `/architect:define-requirements` への橋渡しとなります。コンテキストごとの**一貫性のヒント（consistency hint）**（`Strong`/`Eventual`/`TBD`）は、アーキテクトのプロセスごとのトランザクションの一貫性分類のシードになります。これはプロダクト側では完全に閉じることができない §1.4 の設計上のギャップであり、アーキテクトがそれを確認またはオーバーライドし、拘束力のある ACID/Saga/Local-Tx の決定を下します。

## Output

`reports/03_domain/domain-map.md`、`reports/03_domain/bounded-contexts.md`（`CTX-` テーブル + コンテキストマップ + コンテキストごとの一貫性のヒントを含む）、および `reports/03_domain/ubiquitous-language.md`。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/ddd-strategic.md` | サブドメイン分類、境界付けられたコンテキスト、コンテキストマッピング |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:define-data-model` | Upstream — コンテキストにグループ化されたエンティティ |
| `/product:define-features` | Upstream — ケーパビリティが境界を定義します |
| `/product:design-api` | Downstream — API がコンテキストを実現します |
| `/architect:define-requirements` | Handoff — 境界付けられたコンテキストを消費します |
| `/product:adapt-change` | ドメインが進化するときにこの Skill を再実行します |
