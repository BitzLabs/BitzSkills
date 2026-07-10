# Rules: API-Led Connectivity (design-api)

`/product:design-api`の参照。データ、ビジネスロジック、チャネルの関心事が分離され再利用可能となるように、論理的なAPIサーフェスを**3つのレイヤー**（MuleSoft API-Led Connectivity）で設計する。レイヤーは*論理的*な設計ツールであり、すべてのAPIに3つすべてが必要なわけではない。

## The three layers

1. **System API** — エンティティに対するクリーンな**CRUD**操作を通じて、システム/データソースを公開する。データドメインごとに1つのSystem API（`ENT-` / Bounded Context (境界づけられたコンテキスト)のストアにマッピング）。基盤となるストレージを隠蔽し、それに触れる唯一のものである。
2. **Process API** — 複数のSystem API（および他のProcess API）を構成することにより、**ビジネスフロー**をオーケストレーションする。ビジネスロジックとクロスエンティティのトランザクション/サーガを保持する。ストレージへの直接アクセスは行わない。
3. **Experience API** — Process API / System APIを**特定のチャネル**（Web、モバイル、パートナー）向けに適合させ、そのジャーニー/画面用のペイロードを形成する。ソースではなくコンシューマーのために最適化する。

```
Experience (channel-optimized)
   └─ Process (business flow / orchestration)
        └─ System (CRUD over entities)
```

## Derivation order

1. **エンティティ × CRUD → System API** — `data-model.md`から、エンティティクラスターごとに1つのSystem API。
2. **ビジネスフロー → Process API** — `feature-list.md`/ジャーニーから、System APIをフローに構成する。
3. **画面/ジャーニー → Experience API** — `ui-mocks/`/ジャーニーから、チャネルごとに調整する。

## Reuse & extensibility rules

- **再利用の最大化**: 1つのProcess APIは**多数の**Experience APIにサービスを提供すべきであり、1つのSystem APIは**多数の**Process APIにサービスを提供すべきである。再利用はレイヤー化の最大の目的である。
- **3つのレイヤーすべてを強制しない**: バッチジョブはProcess + Systemのみである可能性がある。自明な読み取りはExperience → Systemである可能性がある。その価値がある場合にレイヤーを追加する。
- **UIにSystem APIを直接公開しない**: チャネルはExperience API（またはProcess API）と通信するため、ストレージはクライアントから分離されたままである。
- **依存関係グラフを非巡回的**かつ下向き（Experience → Process → System）に保つ。

## Per-API specification

各API（`API-` id）について以下を記録する：レイヤー、名前、目的、それが依存するエンティティ/API、および**OpenAPI (OAS)のスケッチ** — 主要なパス、メソッド、主なリクエスト/レスポンスの形状。

## ID convention

レイヤーでタグ付けされた`API-` id。アップストリームの`ENT-`/`FEAT-`/`CTX-`参照とともに`work/traceability.json`に追加する。カタログはクロスAPIの依存関係グラフも記録する。

## Sources

- MuleSoft — "API-Led Connectivity" (System / Process / Experience API)
- OpenAPI Specification — APIごとのスケッチ用
