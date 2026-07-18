# API 設計（API-Led Connectivity 3層）

docs/03_設計仕様/公開API.md の proposed ドラフトを作るための手法。データ・ビジネスロジック・チャネルの関心を分離し再利用可能にする**論理**設計。すべての API に3層が要るわけではない。

## 3層

```
Experience（チャネル最適化）
   └─ Process（ビジネスフロー/オーケストレーション）
        └─ System（エンティティへの CRUD）
```

1. **System API** — 1データドメイン（エンティティ群/コンテキストのストア）につき1つ。ストレージを隠蔽し、ストレージに触る唯一の層
2. **Process API** — 複数の System API を合成してビジネスフローを実現する。ビジネスロジックとエンティティ横断のトランザクション/Saga はここ。ストレージ直アクセス禁止
3. **Experience API** — 特定チャネル（web / mobile / partner）向けにペイロードを整形する。提供元でなく消費者に最適化する

## 導出順序

1. エンティティ × CRUD → System API（ドメインモデルから）
2. ビジネスフロー → Process API（機能一覧・ジャーニーから System API を合成）
3. 画面/ジャーニー → Experience API（チャネルごとに）

## 再利用と拡張の規則

- **再利用の最大化**: 1つの Process API が多数の Experience API に、1つの System API が多数の Process API に仕えるのが層構造の目的
- **3層を強制しない**。バッチは Process + System のみ、自明な読み取りは Experience → System 直結でよい。層はコストに見合うときだけ足す
- **System API を UI に直接公開しない**。チャネルは Experience（または Process）とだけ話す
- 依存グラフは**非循環かつ下向き**（Experience → Process → System）に保つ

## API ごとの記録

各 API について: 層 / 名前 / 目的 / 依存するエンティティ・API / **OpenAPI スケッチ**（主要パス・メソッド・リクエスト/レスポンスの骨子）。カタログには API 間依存グラフも記録する。

## ドラフトへの落とし込み

docs/03_設計仕様/公開API.md（proposed）には層別カタログ（表）+ 依存グラフ + 主要 API の OAS スケッチを書く。導出の作業表（エンティティ×CRUD 対応など）は `.spec/design/` に残す。エンドポイント契約は後段で FR（example-test / pbt）に派生する前提で、入出力を観測可能に書く。
