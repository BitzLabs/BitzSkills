### SDDとDDDオプションの統合に関する詳細技術仕様書

#### 1\. DDDオプション連携の基本思想と「オプトイン」設計

AIを活用した仕様書駆動開発（Spec-Driven Development: SDD）において、最大の技術的障壁は生成AI特有の「文脈の混線（Context Rot）」と、ドメイン知識の欠如による「設計のハルシネーション」です。これらの課題に対し、ドメイン駆動設計（DDD）は、AIが解釈すべき境界を物理的・論理的に固定する最強の「戦略的ガードレール」として機能します。

##### 「オプトイン」設計の合理性

全ての開発に重厚なDDDを適用することは、AIのトークン消費を増大させ、不要なボイラープレート（DTO、変換マッパー等）を量産する「オーバーエンジニアリング」の温床となります。本仕様書では、単純なCRUD処理には軽量なSDDを適用し、複雑なビジネスロジックを伴うコンポーネントのみにDDDを適用する「選択的統合（オプトイン）」を推奨します。これにより、AIの推論リソースを真に重要なドメイン保護に集中させることが可能になります。

##### GSD-antigravityおよびcc-sddとの整合性

DDDオプションは、GSD-antigravityやcc-sddが定義する「Project Memory」および「Gate 1-5」のライフサイクルにおいて、以下の役割を担います。

* **意味的な境界（Semantic Boundary）:**  境界づけられたコンテキストを定義することで、AIエージェントが触れるべき「変更影響範囲（Blast Radius）」を物理的に限定します。  
* **Project Memoryの構造化:**  ユビキタス言語を辞書化し、メモリバンク・プロトコルに基づいて .specs/ フォルダへ永続化することで、AIの「物忘れ」による命名揺れやハルシネーションを完全に封じ込めます。このアーキテクチャの連続性を保証する「単一の真実（SSoT）」が、次に詳述する DOMAIN.md です。

#### 2\. ドメイン知識定義ファイル（DOMAIN.md）の構造仕様

DOMAIN.md は、要求仕様（REQ）と詳細仕様（TECH）の間に位置し、ドメイン知識をAIにとって「唯一の正（Single Source of Truth）」として固定するための重要ドキュメントです。

##### YAMLフロントマターの定義

AIが依存関係グラフ（DAG）を構築し、Spec Validator プラグインがバリデーションを行うためのメタデータを定義します。  
\---  
id: DOMAIN-001  
type: domain\_model  
title: 注文管理ドメインモデル  
status: approved  
version: 1.0.0  
relations:  
  parent: REQ-001  
  children: \[TECH-001, TECH-002\]  
  dependencies: \[DOMAIN-BASE-TYPES\] \# DAGバリデーション用  
  implements: \[src/Domain/Orders/\]  
  tests: \[tests/Domain/OrdersTests/\] \# トレーサビリティ用  
\---

##### ユビキタス言語辞書

命名の揺れを排除し、AIのプロンプト生成における用語選択を固定します。| 用語 | 定義 | コード上のエイリアス || \------ | \------ | \------ || 注文 | 顧客が商品を確定させた契約単位 | Order || 注文明細 | 注文に含まれる個々の商品と数量 | OrderLine || 支払完了 | 決済システムから入金が確認された状態 | PaymentCompleted |

##### 境界コンテキストのマッピング

EARS-AIタグを用いて、AIエージェントに「境界（Boundary）」を明示します。

* **BOUNDED\_CONTEXT: Sales** : 顧客注文を受け付ける論理境界。  
* **BOUNDED\_CONTEXT: Inventory** : 在庫引き当てを管理する論理境界。

##### コンテキストマップ（Mermaidダイアグラム）

コンポーネント間の関係性とイベントフローを視覚化します。  
graph TD  
    Sales\[Sales Context\] \-- "\[DOMAIN\_EVENT: OrderPlaced\]" \--\> Inventory\[Inventory Context\]  
    Inventory \-- "\[DOMAIN\_EVENT: StockReserved\]" \--\> Sales

#### 3\. EARS-AIにおけるDDD戦術的パターンの拡張タグ定義

AIが「単なるデータ構造（DTO）」と「不変条件を持つドメインオブジェクト」を峻別できるよう、EARS-AI構文を拡張します。

##### 拡張タグの定義と制約

* **VALUE\_OBJECT: {Name}** : 不変性（Immutability）と等価性を強制。  
* Mapping: C\# (record), Python (@dataclass(frozen=True))  
* **ENTITY: {Name}** : 識別子（Identity）による同一性保証。  
* **AGGREGATE\_ROOT: {Name}** : トランザクション境界。外部からの直接操作を禁止し、整合性を維持。  
* **DOMAIN\_EVENT: {Name}** : 状態変化の通知。非同期連携のトリガー。  
* **DOMAIN\_SERVICE: {Name}** : 複数オブジェクトに跨る純粋なビジネスロジック。

##### EARS-AI構文の入れ子（Nesting）実装例

AIに対し、ドメインオブジェクト内の振る舞いを構造的に指示します。  
\#\#\# \[AGGREGATE\_ROOT: Order\]  
\* \*\*\[BUSINESS\_RULE\]\*\* 注文合計金額は常に正の数であること。  
\* \*\*\[WHEN\]\*\* \`\[EVENT: PaymentCompleted\]\` が発生した場合  
    \* \*\*\[THEN\]\*\* \`{Order}\` の \`Status\` を \`Paid\` に更新する  
    \* \*\*\[THEN\]\*\* \*\*\[DOMAIN\_EVENT: OrderPaidEvent\]\*\* を発行する  
\* \*\*\[CONSTRAINT\]\*\* \`{OrderLine}\` の追加は必ず \`{Order}\` メソッドを経由すること。

#### 4\. 品質管理ゲート（Gate 2, Gate 4）によるDDD境界チェックの自動化

人間によるレビュー負荷を軽減するため、専用の品質管理プラグインによる自動監査を組み込みます。

##### Gate 2: 詳細設計承認

Architecture & Traceability Reviewer と Spec Validator が以下の整合性を検証します。

* TECH\_SPEC で定義されたクラス構造が DOMAIN.md のユビキタス言語に準拠しているか。  
* 集約ルート（AGGREGATE\_ROOT）の境界設定が適切であり、不適切なプロパティ公開がないか。

##### Gate 4: 仕様・実装突合検証（Two-Tier Verification）

Two-Tier Compliance Checker プラグインを用い、二段階で検証します。

* **Phase A: 構造検証 (Structural Verification)**  
* 実装されたクラス、APIシグネチャ、型定義が TECH\_SPEC のデータ契約（Contracts）と完全に一致しているかを静的解析。  
* **Phase B: 振る舞い検証 (Behavioral Verification)**  
* 実行されたテストが REQ の受入基準（Acceptance Criteria）および DOMAIN.md のビジネスルールを100%網羅しているかをAI推論でマッピング。境界違反が検出された場合、Self-Healing Synchronizer が「集約ルートを無視した直接操作です。メソッド経由に変更してください」といった具体的なリファクタリング指示を出し、自動リトライサイクルを回します。

#### 5\. テスト駆動開発（TDD）とドメイン層の隔離優先実装

インフラストラクチャへの依存を排除し、純粋なドメインロジックの正当性を保証するための「ドメイン層隔離優先」ルールを適用します。

##### POCO/POJOによるドメイン実装と物理的隔離

ドメイン層は、データベース、API、UIに一切依存しないプレーンなオブジェクトとして実装します。この際、.specs/ フォルダ（Memory Bank領域）にドメイン定義を物理的に隔離し、External Brain Digest として管理することで、AIがインフラ層の関心をドメインに漏洩させることを防ぎます。

##### TDDによる仕様ドリフト防止

AGGREGATE\_ROOT や VALUE\_OBJECT の制約に基づき、実装コードより先に単体テストを自動生成します。

* **戦略的価値:**  実装より先にテストを生成することは、AI開発における「仕様ドリフト（Spec Drift）」を抑制するための最大のガードレールです。

##### 依存関係逆転の原則 (DIP) の適用

インフラ層がドメイン層に依存する構造を維持します。フロントマターの implements フィールドを用い、AIに対して「このインターフェースの具象実装はインフラ層で行い、ドメイン層は純粋な契約のみを保持せよ」と明示的に指示します。

##### 結論

本仕様書が定義するDDDオプションの統合は、AIを単なるコード生成器から「ビジネスルールを遵守する熟練アーキテクト」へと昇華させるものです。DOMAIN.md による厳格な境界定義と、Gate 4における二段階検証が、AI時代における持続可能な高品質コードの生成を約束します。  
