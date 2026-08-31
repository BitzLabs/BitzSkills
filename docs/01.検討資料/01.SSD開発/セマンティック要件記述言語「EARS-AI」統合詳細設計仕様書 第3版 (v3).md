### セマンティック要件記述言語「EARS-AI」統合詳細設計仕様書 第3版 (v3)

#### 1\. はじめに：EARS-AIの戦略的意義と背景

AIエージェントによる自動実装（Autonomous Implementation）において、従来の自然言語による仕様記述は、ハルシネーションと開発効率低下の主因となっている。特に、従来の仕様書で多用される「shall（〜するものとする）」という単一の助動詞は、AIにとって「決定論的なシステム応答（Deterministic Implementation）」と「非決定論的な推論・生成（Non-deterministic Inference）」、あるいは「厳格なガードレール（Constraint）」の区別を不可能にさせている。この曖昧さはAIのコンテキストウィンドウ内でのエントロピーを増大させ、結果として仕様と実装の乖離（Spec Drift）を招く。本仕様書が定義する「EARS-AI」は、従来のEARS（Easy Approach to Requirements Syntax）を情報アーキテクチャの観点から再構築し、AIの「Attention（注意機構）」を最大化するためのセマンティック構造である。特定のセマンティックタグを「意味論的アンカー（Semantic Anchors）」として機能させることで、Transformerモデルにおけるトークンの重み付けを最適化し、高エントロピーな推論を排除した確実な実装を強制する。これより、仕様書を「AIが解釈可能な実行コードの設計図」へと昇華させることが本仕様の戦略的価値である。

#### 2\. アーキテクチャ原則：3レイヤーアクターと職務分掌

AIエージェントが「誰の管轄で」「何を」実行するかを厳密に分離するため、EARS-AIでは以下の3レイヤーアクターモデルを定義する。

##### 2.1 3レイヤーアクターモデル

1. **Human (決定権者 / USER):**  要求の起点であり、ビジネス価値の承認権を持つ。AIに対する最終的なゲートキーパー。  
2. **AI (実行・提案者 / AGENT):**  仕様の翻訳、タスク分解、コード生成、同期を担当する自律エージェント。  
3. **Target (操作対象システム / SYSTEM):**  実装対象のコードベース、API、DBなどの操作対象物。

##### 2.2 職務分掌（Separation of Duties）の原則

AIエージェントによる「自己承認」を防止し、システムの堅牢性を担保するため、以下のメカニズムを強制する。

* **権限隔離:**  実装を行うAI（Implementer）と、検証を行うAI（Validator/Reviewer）を物理的に分離し、独立したスキルセット（プラグイン）を割り当てる。  
* **論理スコープ・コンテナ:**  Markdownのリストネスト構造を利用し、AIに対する「論理的なスコープ隔離」を視覚化・構造化する。

##### 2.3 Markdownネストによるスコープ隔離

Markdownのインデント（ネスト）は、AIにとっての「変数・アクターの可視性境界（Visibility Boundary）」として機能する。

* ACTOR: Human  
* ACTION: Approve  
* TARGET: REQ-001  
* ACTOR: AI  
* ACTION: Generate  
* TARGET: TECH-001  
* CONSTRAINT: Always use clean architecture patternsこの階層構造により、特定のアクターが影響を及ぼせる範囲を明確化し、自律実行時における職務分掌違反を構造的に排除する。

#### 3\. EARS-AI 構文仕様：shallの解体とセマンティックタグ

従来の曖昧な「shall」を廃止し、AIに対する制約力とコード変換時の性質（AST解析への適合性）に基づき、4つのセマンティックタグへ分解する。

##### 3.1 セマンティックタグ定義

タグ,意味論的定義,AIに対する制約力,コード変換時の性質（AST）  
THEN,決定論的なシステム応答,強  (絶対実行),関数ロジック、If-Then、状態遷移  
CONSTRAINT,静的・非機能・品質制約,最優先  (ガードレール),Linter、型定義、アーキテクチャ規約  
GENERATE,非決定論的なAI自律アクション,中  (推論・生成許容),生成プロンプト、データ補完、LLM呼出  
ALWAYS,普遍的なビジネスルール,不変  (基盤ルール),定数、不変条件 (Invariants)、ドメイン制約

##### 3.2 構文パターンの定義

AIが仕様をパースする際の認識精度を最大化するため、以下の構文パターンを規定する。

* **Ubiquitous (普遍):**  ALWAYS {システム} は \<アクション\> する  
* 全状態で有効なビジネスルール。  
* **Event (イベント):**  WHEN {イベント} が発生した場合 THEN {システム} は \<アクション\> する  
* リアクティブな動作。  
* **State (状態):**  WHILE {状態} である間 THEN {システム} は \<アクション\> する  
* コンテキスト依存の振る舞い。  
* **Unwanted Behavior (異常系):**  IF\_ERROR {例外条件} THEN \<リカバリー処理\>  
* AIにTry-Catchや例外ハンドリングを強制する。  
* **Optional (任意要件):**  WHERE {前提条件・コンポーネント} が存在する場合 THEN \<アクション\>  
* 特定条件下でのみアクティブ化される機能。  
* **Complex (複合):**  上記パターンの組み合わせ。AIに高度な依存関係推論を要求する。

#### 4\. DDD（ドメイン駆動設計）オプションの完全統合

AIのコンテキストウィンドウ内での「意味の混線（Context Rot）」を防ぐ最強のガードレールとして、DDD戦術的パターンのタグ拡張を規定する。

##### 4.1 DDDタグの定義

* **AGGREGATE\_ROOT** : トランザクションと整合性の境界。AIに対し、この内部エンティティへの直接操作を禁止する。  
* **ENTITY** : 一意識別子を持つオブジェクト。ライフサイクル管理をAIに強制する。  
* **VALUE\_OBJECT** : 不変性（Immutable）を持つ値。副作用のない計算ロジックのみを許可する。  
* **DOMAIN\_EVENT** : ドメイン内で発生した重要事象。他サービスへの通知をAIに実装させるトリガー。  
* **DOMAIN\_SERVICE** : 複数の集約にまたがる業務ロジックの定義。これらのタグを付与することで、AIは「これは単なるデータ構造ではなく、厳格な振る舞いを持つドメインオブジェクトである」と認識し、勝手なCRUD実装を抑制する。

#### 5\. ドキュメント構造とトレーサビリティ：Frontmatter & DAG

仕様書間の依存関係を機械可読にするため、YAML Frontmatterを用いた「仕様の有向非巡回グラフ（DAG）」を構築する。

##### 5.1 Frontmatter スキーマ例

id: TECH-001  
title: 配線インピーダンス計算ロジック  
type: technical\_spec \# requirement | technical\_spec | milestone | issue  
status: implementing \# draft | review | approved | implementing | verified  
version: 1.1.0  
milestone: MS-001  
issues: \["\#42"\]  
relations:  
  parent: REQ-001  
  children: \[\]  
  dependencies: \[TECH-000-COMMON\]  
  implements: \[src/Calculators/Impedance.cs\]  
  tests: \[tests/ImpedanceTests.cs\]

##### 5.2 コンテキスト・プルーニングとSpec Drift防止

* **Context Pruning:**  フロントマターにより構築されたDAGを辿ることで、AIは現在のタスクに関連する最小限の仕様ブランチのみをロードする。これによりトークン消費を抑え、AIの注意を特定のタスクに集中させる。  
* **Spec Drift 防止:**  implements フィールドによりコードと仕様を1対1でマッピングする。後述する sdd sync により、実装と仕様の整合性を機械的に担保する。

#### 6\. 実装エンジンの詳細設計：sdd CLI とスキルプラグイン

仕様書の「コンパイル」と開発サイクルの自動化を担当するPythonベースのスキルプラグイン群の設計を以下に規定する。

##### 6.1 sdd CLI コマンド体系

* **sdd lint** : 依存関係の欠落、EARS-AI構文エラー、ステータスの矛盾（親が未承認なのに子が実装中など）を静的解析する。  
* **sdd design** : REQを入力とし、プロジェクト憲章に基づいたTECHの下書きを自動生成する。  
* **sdd bdd-sync** : REQの受入基準からGiven/When/Then形式のテストスタブを自動生成する。  
* **sdd spike** : プロトタイプコードから事後的にREQ/TECHを逆生成（リバースエンジニアリング）する。  
* **sdd sync (Self-Healing)** : 実装コードの git diff を解析し、変更点を implements フィールドに基づきTECHへ逆反映する。AIは「蒸留プロンプト（Distillation Prompt）」を用い、実装の枝葉を削ぎ落として本質的な設計変更のみを仕様書に反映させる。

#### 7\. 完全仕様書サンプル：配線インピーダンス計算

##### 7.1 要求仕様書 (REQ-001.md)

\---  
id: REQ-001  
type: requirement  
status: approved  
milestone: MS-001  
\---  
\# \[REQ-001\] 配線インピーダンス計算機能

\#\# 1\. 目的  
電線情報に基づく電圧降下率の自動算出を実現し、設計工数を削減する。

\#\# 2\. ビジネスルール (EARS-AI)  
\* \[ACTOR: 設計者\]  
    \* \[CAPABILITY\] 電線種別、断面積、こう長を入力し計算を実行できる。  
\* \[ALWAYS\] 計算はJIS/内線規程に基づく温度補正を適用すること。  
\* \[CONSTRAINT\] 算出結果は有効数字3桁で出力すること。

##### 7.2 詳細仕様書 (TECH-001.md)

\---  
id: TECH-001  
type: technical\_spec  
status: implementing  
relations:  
  parent: REQ-001  
  implements: \[src/Models/Impedance.cs\]  
\---  
\# \[TECH-001\] インピーダンス計算ロジック詳細

\#\# 1\. データモデル (DDD)  
\* \*\*\[VALUE\_OBJECT: Impedance\]\*\*  
    \* \[PROPERTY: double Resistance\]  
    \* \[PROPERTY: double Reactance\]  
\* \*\*\[ENTITY: CalculationSession\]\*\*  
    \* \[PROPERTY: string SessionId\]  
    \* \[INIT\_STATE\] \`Idle\`  
    \* \[STATE: Idle\]  
        \* \[WHEN\] \`Calculate\` 発行 \[THEN\] \*\*\[NEXT\_STATE: Calculating\]\*\*  
    \* \[STATE: Calculating\]  
        \* \[WHEN\] \`Success\` \[THEN\] \*\*\[NEXT\_STATE: Completed\]\*\*  
        \* \[IF\_ERROR\] \`Timeout\` \[THEN\] \*\*\[NEXT\_STATE: Failed\]\*\*

\#\# 2\. 振る舞い定義 (EARS-AI)  
\* \[WHEN\] 計算処理が実行された場合  
    \* \[THEN\] 以下の温度補正公式を適用する：  
        \`Rt \= R20 \* (1 \+ 0.00393 \* (t \- 20))\`  
    \* \[THEN\] \`TotalZ \= sqrt(Rt^2 \+ X^2)\` を算出する。  
\* \[IF\_ERROR\] \`LengthMeters \<= 0\` の場合  
    \* \[THEN\] \`ArgumentOutOfRangeException\` を送出する。  
\* \[WHERE\] \`AmbientTemperature\` が指定されない場合  
    \* \[THEN\] デフォルト値 \`20.0\` を適用する。

#### 8\. 品質管理とガバナンス：5段階の検証ゲート

SDDサイクルでは、以下のゲートを通過することで品質を保証する。

1. **Gate 1 (要件妥当性):**  REQの曖昧さをAIが排除し、人間がビジネス要件を承認。  
2. **Gate 2 (設計整合性):**  REQとTECHのリンク、DDDモデルの妥当性を検証。  
3. **Gate 3 (自律実装):**  sdd-cliによるTDDサイクル。  
4. **Gate 4 (仕様突合):**  二段階検証（Two-Tier Verification）。実装されたクラス構造（Structure）がTECHと一致し、テストされた振る舞い（Behavior）がREQを満たしているか監査。  
5. **Gate 5 (リビングスペック監査):**  sdd sync による逆同期。コードと仕様の乖離をゼロに保ち、マージを許可する。EARS-AI v3の導入により、仕様書は単なる記録から「Single Source of Truth（唯一の正）」へと進化する。これにより、AI駆動開発における確実なガバナンスと、航空宇宙・産業制御レベルの信頼性を実現する。

