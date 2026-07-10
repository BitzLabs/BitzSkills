# Rules: Strategic DDD (define-data-model, map-domains)

データモデルを導出する際、およびフェーズ4でのBounded Context (境界づけられたコンテキスト)において使用される、戦略的DDD (Domain-Driven Design)の概念のリファレンスである。モデルは常に**Ubiquitous Language (ユビキタス言語)**に基づいている必要がある。

## Building blocks (tactical, used in the data model)

- **Entity (エンティティ)** — 状態の変化を通じて持続する同一性（属性値ではなくキーによって追跡される）を持つ。概念が永続化され、識別され、複数の操作を受け入れる場合にのみ、その概念をエンティティに昇格させる。
- **Value Object (値オブジェクト)** — 属性によって定義され、同一性を持たず、不変である（例：Money、Address、DateRange）。過剰な正規化を避けるため、エンティティよりもValue Objectを優先する。
- **Aggregate (集約)** — 1つの整合性の単位として扱われるエンティティ/Value Objectのクラスター。**Aggregate Root (集約ルート)**が唯一のエントリポイントであり、不変条件はAggregateの境界内で保持される。
- **Command → Aggregate → Event** — Command (コマンド)が変更を要求し、Aggregateが不変条件を強制してそれを適用し、Event (イベント)がそれが発生したことを記録する。これがエンティティの発見を促進する。

**トランザクションの境界 = Aggregateの境界である。** Aggregateは小さく保ち、他のAggregateを参照する際は、直接のオブジェクト包含ではなく、IDによる参照を行うこと。

## Strategic design (used by map-domains in Phase 4)

- **Ubiquitous Language** — コード、ドキュメント、および会話で使用される、コンテキストごとに共有される1つの正確な語彙。すべての`ENT-`/用語はそこに現れる必要がある。
- **Bounded Context** — モデルとその言語が一貫している明示的な境界。同じ単語が異なるコンテキストで異なる意味を持つことがあるが、それは想定内である。それぞれに`CTX-` IDが付与される。
- **Subdomain (サブドメイン)の分類** — 問題領域を分割する：
  - **Core (コアドメイン)** — 差別化をもたらすドメインであり、競争優位性が存在する場所。**ここに投資し**、購入するのではなく構築する。
  - **Supporting (サポートサブドメイン)** — 必要だが差別化にはならないもの。実用的に構築する。
  - **Generic (汎用サブドメイン)** — 解決済みの問題（認証、請求、通知など）。**過剰にエンジニアリングせず、購入/採用する**。
- **Context mapping (コンテキストマッピング)** — コンテキスト間の関係（Partnership、Customer/Supplier、Conformist、**Anticorruption Layer (腐敗防止層)**、**Open Host Service (公開ホストサービス) / Published Language (公開言語)**、Shared Kernel）。コンテキスト間の疎結合を目指し、ACL（Anticorruption Layer）でCoreを保護する。
- **拡張性のための境界サイジング** — 将来の機能を取り込みやすい境界を描く。変更に耐えられるよう、現在の画面ではなくビジネス機能にコンテキストを合わせる。
- **コンテキストごとの一貫性のヒント** — 各`CTX-`に大まかな`Strong` / `Eventual` / `TBD`のヒントをタグ付けする（不変条件を持つコンテキスト — お金、在庫、予約 → `Strong`。リードモデル、分析、通知 → `Eventual`）。これはアーキテクトのトランザクション分類の種となる*ヒント*であり、拘束力のある決定ではない。

## Handoff to nexus-architect

`CTX-`のBounded ContextとUbiquitous Languageは、アーキテクトのBounded Contextの入力（design.md §1.3）にマッピングされる。`map-domains`の出力は`/architect:define-requirements`へのブリッジである。コンテキストごとの一貫性のヒントは、アーキテクトのプロセスごとのトランザクション一貫性の分類（design.md §1.4）の種となり、それがバインディングとなるACID/Saga/Local-Txの決定を行う。

## Discipline

- データベーススキーマではなく、**ドメイン**をモデル化する。ストレージはモデルに従わせる。
- 都合が良いからといってドメインモデル貧血症（anemic model）を避けるが、要件に必要のない振る舞いを発明してはならない。
- 各Aggregate/エンティティの境界の根拠を記録し、`adapt-change`で再検討できるようにする。

## ID convention

エンティティ（データモデル）には`ENT-`、ドメイン/Bounded Context（フェーズ4）には`DOM-`/`BC-`を使用する。上流の`FEAT-`/`JOB-`への参照を伴って`work/traceability.json`に追記する。

## Sources

- Eric Evans — "Domain-Driven Design" (entities, value objects, aggregates, ubiquitous language)
- Vaughn Vernon — "Implementing DDD" (aggregate design rules, context mapping)
