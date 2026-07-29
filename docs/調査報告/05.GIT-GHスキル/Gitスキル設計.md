# **自律型LLMエージェント向け共通Git操作スキルの設計とトークン最適化に関する研究報告書**

## **背景とシステム課題**

自律型LLMエージェント（Agy、Codex、Claude Codeなど）によるソフトウェア開発の自動化において、コードの変更履歴管理や実行結果の検証を目的としたGit操作は不可欠な要素技術となっている1。しかし、既存のエージェントシステムにおけるGit操作の多くは、エージェント自身が動的にコマンドラインスクリプトを生成し、その実行出力をパースして検証を行うというアドホックな設計に依存している3。このアプローチは、システムの信頼性、実行の均一性、そして何よりも運用コストの観点から極めて非効率的である2。  
動的なスクリプト生成方式には、主に三つの深刻な課題が存在する。第一に、LLMの推論における非決定性により、実行されるGit操作の品質や例外処理能力がモデルの性能に直接左右され、動作の均一性が失われることである5。第二に、エージェントの作業履歴（Trajectory）が累積するにつれてコンテキストウィンドウが急激に消費され、APIコストの指数関数的な増大を招くことである1。マルチターン実行モデルにおける実行履歴は、タスク開始時に数キロトークンであっても、履歴の蓄積によって容易に百万トークンを超える規模に達する2。統計データによれば、実稼働環境におけるエージェントのトークン消費の約99%は累積されたコンテキスト入力トークンであり、LLMが実際に生成する出力トークンはわずか1%にすぎない1。第三に、生のシェルを介した操作は、認証トークンや秘匿情報の漏洩リスクを高めるなど、セキュリティ上の懸念を増大させることである6。  
さらに、Git操作をエージェントの外部「ツール（Skill）」として定義する際にも、標準的なModel Context Protocol（MCP）などのフレームワークを単純に適用すると、別のトークン消費ボトルネックが発生する6。LLMのAPIはステートレスであるため、リクエストのたびに利用可能なすべてのツール定義（JSON Schema）を送信する必要がある6。例えば、40個のGitツールを搭載したMCPサーバーを使用する場合、毎回のやり取りで10キロバイトから15キロバイトの不必要なスキーマ情報がコンテキストに付加され、トークンオーバーヘッドを深刻化させる6。  
本報告書では、これらの課題を克服するため、どのモデルからも均一なGit操作を保証し、かつ情報のセマンティクスを損なうことなくトークン消費を極限まで抑制する「共通Git操作スキル」の要求仕様から詳細設計までを論じる。

## **要求仕様の定義**

本システムが目指すのは、アドホックなスクリプト実行を完全に排除し、安全、軽量、かつモデル非依存なGit操作をエージェントに提供することである3。以下に、システムの構築に必要な機能要件および非機能要件を定義する。

### **機能要件**

共通Git操作スキルが備えるべき具体的な機能要件を以下の通り定義する。

* **モデル非依存の統合インターフェース**: AgyやCodexといった異なるエージェントアーキテクチャ、あるいはClaude、GPT、ローカルLLMなどの多様なモデルから、均一なプロトコルで呼び出せる共通APIを提供する6。  
* **コア操作の隠蔽と抽象化**: status、diff、log、commit、push、pullなどの主要なGit操作を独立した高レベルの関数（Skill）として定義し、エージェントによる生のシェルスクリプト生成を不要にする3。  
* **戻り値の自律的セマンティック圧縮**: 生のCLI出力をそのまま返すのではなく、不要なノイズを除去し、エージェントの意思決定に必要な本質的情報のみに構造化・圧縮して返却する3。  
* **セキュリティ・コンプライアンス管理**: エージェントに認証情報を直接扱わせず、プロキシレイヤーまたは実行コンテキストのバックエンド側で認証処理を完全に隠蔽・制御する6。

### **非機能要件**

システムの運用効率とコストを最大化するための非機能要件を以下の通り定義する。

* **トークン削減性能**: Git関連操作における平均トークン消費量を、生のCLI実行時と比較して、コマンドごとに最低でも70%から90%以上削減する3。  
* **KVキャッシュの保護とアライメント**: コンテキストの変動によるプロンプトキャッシュ（KV Cache）の無効化を最小限に抑えるため、入力メッセージの接頭辞（Prefix）を固定化し、トークンのヒット率を最大化する設計とする2。  
* **低遅延処理**: Gitコマンドの実行、およびそれに続く出力の圧縮・要約処理は、エージェントの推論ターンを阻害しないよう極めて低遅延（ミリ秒単位）で実行される3。

これらの要件を満たすために設計された共通Gitスキルの構成要件を、下表に取りまとめる。

| スキル識別子 | 対象Git操作 | 必須要件とセマンティックの維持方針 | トークン削減アプローチ |
| :---- | :---- | :---- | :---- |
| git\_status | git status | 変更・未追跡ファイルのパスと編集状態の維持11 | ヘルプテキストや装飾枠、余白の完全除去3 |
| git\_diff | git diff | 変更論理構造（どの関数・クラスがどう変わったか）の維持12 | 行レベル・ハンクレベルの圧縮、コンテキスト行の削減12 |
| git\_log | git log | コミットの流れとブランチトポロジーの維持13 | メタデータの削除、1行ずつの極小コミット表現への置換3 |
| git\_write | git commit/push/pull | 実行結果の成否（成否ステータス）の維持3 | 詳細な通信・進捗ログを遮断し、確定シンボルのみ応答3 |

## **トークン削減と出力簡素化の詳細設計**

エージェントのコンテキスト内において不必要なトークンの蓄積を防ぐため、本システムでは「情報価値の密度」に着目したフィルタリングと圧縮手法を導入する3。実行軌跡における無駄は、本質的に「無用な情報（Useless）」、「重複した情報（Redundant）」、「期限切れの情報（Expired）」の三つの特性に分類できる2。

### **軌跡情報における無駄の三要素と対策**

* **無用な情報（Useless）の排除**: テストログ、ビルド出力、あるいは .pycache などの一時ファイルやリソースファイルの列挙など、エージェントの目的達成に全く寄与しないデータを指す2。Git操作においては、git status が提示する「ファイルをインデックスに追加するためのコマンド例」などの説明文がこれに該当する11。本設計では、これら非セマンティックなテキストをルールベースの正規表現を用いてミリ秒単位で一括除去する3。  
* **重複した情報（Redundant）の排除**: 差分表示において、同一のコード断片が「変更前」と「変更後」で何度も繰り返してコンテキストに送られる状況を指す2。特にコードブロック置き換え系のツールでは、古いコードと新しいコードの双方が二重に軌跡へ蓄積される2。本スキルでは、抽象構文木（AST）解析またはハッシュベースの重複検知を用いて、履歴内の冗長な変更ブロックを単一の表現に縮退させる10。  
* **期限切れの情報（Expired）の管理**: 探索フェーズにおいて、ある不具合の原因を特定するために実行した大量の git diff やファイル閲覧のログは、原因箇所が特定された瞬間に「目的を果たした過去のノイズ」と化す2。本設計では、タスク進行に伴い重要性の低下した過去のGit実行履歴をエージェントのコンテキストから自動的にロールアップ（要約）または物理除去し、最新の状態（Current-State）のみをコンテキストの前面に維持する13。

### **コマンド別最適化処理のメカニズム**

Gitコマンドの出力を圧縮するための具体的なロジックを以下のように設計する3。

#### **1\. ステータス情報の極小化**

git status の生出力から、ブランチ間の位置関係、変更されたファイルの相対パス、および編集ステータス（変更、追加、削除、未追跡など）のみを抽出し、以下のように変換する11。

# **生出力（約 150 トークン）**

11  
On branch main  
Your branch is up to date with 'origin/main'.  
Changes not staged for commit:  
(use "git add ..." to update what will be committed)  
(use "git restore ..." to discard changes in working directory)  
modified: src/core.py  
Untracked files:  
(use "git add ..." to include in what will be committed)  
tests/test\_core.py  
no changes added to commit (use "git add" and/or "git commit \-a")

# **圧縮出力（約 10 トークン）**

11

* main...origin/main  
  M src/core.py  
  ?? tests/test\_core.py

#### **2\. 再帰的差分解剖（Recursive Dissection）による差分圧縮**

変更量の大きい git diff に対しては、単に全体のテキストを受け渡すのではなく、以下の4段階のレイヤーでセマンティック圧縮を試みる12。

\[ Raw Git Diff \]  
       │  
       ▼ (Level 1\) Greedy File Packer: ファイル単位の重要度仕分けと選別  
\[ 重要ファイルの抽出 \]  
       │  
       ▼ (Level 2\) Hunk-Level Splitter: 差分塊（Hunk）の分離とメタデータの適用  
\[ 変更ブロックの孤立化 \]  
       │  
       ▼ (Level 3\) Smart Line Slicing: コンテキスト行の削減、不変な定型文の排除  
\[ 最小限の変更境界 \]  
       │  
       ▼ (Level 4\) Binary Search / CCR: 超過データのローカルキャッシュ退避とインデックス置換  
\[ 圧縮されたDiffオブジェクト \]

* **Greedy File Packer**: 変更されたファイルを走査し、重要性の低い自動生成ファイル、依存関係ロックファイル（package-lock.json や Cargo.lock など）の差分をすべて遮断する12。これらはファイル名と変更行数のみのメタデータに要約される12。  
* **Hunk-Level Splitter**: 差分をパースし、各差分ブロック（Hunk）がどのクラスや関数に属しているかを特定した上で、不要な境界メタデータをそぎ落とし、ファイルヘッダー情報を一度だけコンテキストに挿入する12。  
* **Smart Line Slicing**: 標準で前後3行出力される不変のコンテキスト行をデフォルトで0行または1行に削減する12。これによって、差分の論理的意味（何が追加され、何が削除されたか）を保ったまま、テキスト量を半分以下に削減する3。  
* **可逆的コンテキスト検索（CCR）の適用**: 差分が事前に設定されたトークンバジェット（例: 500トークン）を超える場合、圧縮されたサマリーを出力すると同時に、生の差分データをローカルにキャッシュする10。エージェントが特定箇所の完全な差分情報を必要とした場合に限り、提供された一意のハッシュキーを用いて部分的に生データを復元取得するツール（retrieve\_raw\_diff 相当）を呼び出す構成とする10。

#### **3\. 書き込み系操作の極小レスポンス**

commit や push などの結果は、エージェントにとって「成否」および「次の行動に必要な一意の識別子（ハッシュなど）」のみが重要であり、進捗メッセージは無駄なノイズである3。

* **git commit**: 生出力をすべて破棄し、"ok \[commit\_hash\]" の形式に固定化して返却する3。  
* **git push / git pull**: ネットワーク通信時の進行ログを全面的にカットし、結果の要約（同期したブランチ名、または差分統計情報の極小サマリー）のみを返す3。

## **共通Git操作スキルのシステム構造設計**

どのLLMエージェントからも、またどのバックエンドモデルからも均一な制御を可能にするため、システム構造は以下の三つの主要なコンポーネントで設計される3。

                         \[ LLMエージェント (Agy/Codex/Claude Code) \]  
                                            │  
                                            ▼ (1) 標準化された関数呼び出し (API Request)   
┌───────────────────────────────────────────┴───────────────────────────────────────────┐  
│ 共通Git操作プロキシ層 (スキル仲介インターフェース)                                     │  
│                                                                                       │  
│  ┌───────────────────────┐   ┌───────────────────────┐   ┌─────────────────────────┐  │  
│  │ MCPスキーマ削減エンジン│   │ キャッシュアライナー  │   │ CCR（可逆キャッシュ）   │  │  
│  │ (Tool Schema Pruning) │   │ (CacheAligner)        │   │ (Local File Cache)      │  │  
│  └───────────┬───────────┘   └───────────┬───────────┘   └────────────┬────────────┘  │  
│              │                           │                            │               │  
│              └───────────────────────────┼────────────────────────────┘               │  
│                                          ▼ (2) 実行制御とトークン圧縮                 │  
│                      \[ フィルター・圧縮処理コア (Rust / Go製) \]                       │  
└──────────────────────────────────────────┬────────────────────────────────────────────┘  
                                           │  
                                           ▼ (3) 安全なサンドボックス上でのGitコマンド実行\[cite: 7\]  
                                 \[ 対象Gitリポジトリ \]

### **1\. スキル仲介インターフェース（プロキシ層）**

エージェントからの関数呼び出しを受け取り、裏でGitコマンドを実行し、結果を圧縮して返却する仲介プロキシとして動作する3。このレイヤーをエージェントとGitリポジトリの間に挟むことで、エージェントがいかなるモデル（GPT、Claude、Geminiなど）で駆動していても、常に同じ入力条件と期待通りの応答を受けることができる6。

### **2\. MCPスキーマ削減エンジン（Tool Schema Pruning）**

エージェントシステム全体で利用可能なMCPツールの数が膨大であっても、Git操作に必要な最小限のツールスキーマだけを動的に選択してLLMの初期プロンプトに注入する6。これにより、システム初期化フェーズにおける最大15KBにおよぶスキーマメタデータのオーバーヘッドを回避し、推論第1ターン目からコンテキスト領域を保護する6。

### **3\. キャッシュアライナー（CacheAligner）とプロンプトキャッシュ統合**

APIプロバイダーが提供するプロンプトキャッシュを最大限に活用するため、Gitスキルの応答メッセージ構造やメタデータの接頭辞フォーマットを厳密に固定化する10。少しでも入力テキストの形式が揺れると、KVキャッシュ全体の再利用率が著しく低下するため、固定ヘッダー（例: \#\#\# GIT\_STATUS\_OUTPUT \#\#\#）と正規化されたパス文字列を用いてアライメントを制御する2。

### **共通Gitスキルのデータ構造定義**

パースされたGit Diff情報を保持し、段階的なセマンティック圧縮を可能にするためのデータモデルを、以下のような構造体（Pydanticモデル仕様をベースとした定義）として設計する16。

Python  
from pydantic import BaseModel, Field  
from typing import List, Optional

class DiffLineModel(BaseModel):  
    """  
    1行単位の差分情報を表現するモデル。  
    """  
    line\_type: str \= Field(..., description="行の種類。'added', 'removed', または 'context'")  
    line\_number: Optional\[int\] \= Field(None, description="変更後の行番号。削除行の場合はNone")  
    content: str \= Field(..., description="コード行の実テキスト")

class DiffHunkModel(BaseModel):  
    """  
    一連の変更箇所（ハンク）を表現するモデル。  
    """  
    old\_start\_line: int \= Field(..., description="古いファイルにおける開始行番号")  
    old\_line\_count: int \= Field(..., description="古いファイルにおける変更行数")  
    new\_start\_line: int \= Field(..., description="新しいファイルにおける開始行番号")  
    new\_line\_count: int \= Field(..., description="新しいファイルにおける変更行数")  
    lines: List\[DiffLineModel\] \= Field(..., description="ハンク内に含まれる差分行のリスト")

class FileDiffModel(BaseModel):  
    """  
    ファイル単位の変更情報を表現するモデル。  
    """  
    old\_filepath: str \= Field(..., description="変更前のファイル相対パス")  
    new\_filepath: str \= Field(..., description="変更後のファイル相対パス")  
    is\_new\_file: bool \= Field(False, description="新規作成されたファイルか否か")  
    is\_deleted\_file: bool \= Field(False, description="削除されたファイルか否か")  
    hunks: List\[DiffHunkModel\] \= Field(..., description="このファイルに含まれるハンクのリスト")

## **導入効果と定量的評価指標**

本アーキテクチャの導入により、エージェントシステムのトークン効率および運用費用がどの程度改善されるかを測定するため、具体的な評価指標と実測ベースのコスト比較を以下に示す3。

### **評価指標の定義**

コスト効率の最適化を測る指標として、以下の「有効トークン数（Effective Tokens: ET）」を用いる6。この指標は、単純なトークンカウンティングとは異なり、APIプロバイダーのキャッシュ割引率や出力トークンの割増コスト特性を統合したものである6。  
![][image1]  
ここで、

* ![][image2] は、キャッシュにヒットせず、通常の満額コストが適用される入力（プロンプト）トークン数6。  
* ![][image3] は、プロンプトキャッシュが機能し、およそ10分の1の格安単価で処理された入力トークン数6。  
* ![][image4] は、LLMが生成した出力（補完）トークン数。出力処理はGPU演算負荷が高く、入力の約4倍の価格が設定されることが多いため、4.0の重みを適用する6。

システム全体の最終的なコストインデックスは、使用するモデルのランクに応じた倍率（![][image5]）をETに乗算して算出される6。  
![][image6]

| 使用モデルの階層 (Tier) | モデル乗数 (M) | 想定される主な役割・タスク |
| :---- | :---- | :---- |
| **Opus Tier** (超大規模推論モデル) | ![][image7] | 高度なアーキテクチャ設計、複雑な衝突（Conflict）の解決6 |
| **Sonnet Tier** (標準的なエージェント用モデル) | ![][image8] | 標準的なコーディング作業、継続的なデバッグタスク6 |
| **Haiku Tier** (軽量高速モデル) | ![][image9] | ルーチンチェック、コミットメッセージの自動生成、進捗監視6 |

### **コマンド別トークン削減効果の比較**

標準的な30分の開発セッションにおいて、エージェントが各開発コマンドを平均的な頻度で実行した場合のトークン消費量を、生のCLI出力と本システム（共通Git操作スキル）経由で比較した予測データを以下の表に示す3。

| 実行される開発操作 | 平均実行頻度 | Raw CLI実行時の消費トークン数（計） | 本システム経由の消費トークン数（計） | 実質的なトークン削減率 |
| :---- | :---- | :---- | :---- | :---- |
| **ls / tree (ディレクトリ一覧確認)** | 10回 | 2,000 | 400 | \-80%3 |
| **cat / read (ファイル内容の読み出し)** | 20回 | 40,000 | 12,000 | \-70%3 |
| **grep / rg (ソースコード内検索)** | 8回 | 16,000 | 3,200 | \-80%3 |
| **git status (変更ファイルの確認)** | 10回 | 3,000 | 600 | \-80%3 |
| **git diff (ソースコード差分確認)** | 5回 | 10,000 | 2,500 | \-75%3 |
| **git log (最近のコミットログ確認)** | 5回 | 2,500 | 500 | \-80%3 |
| **git commit/push/pull (履歴同期)** | 8回 | 1,600 | 120 | \-92%3 |

この削減効果により、システム開発ベンチマーク（SWE-benchなど）において、入力トークンを全体として39.9%から59.7%削減し、推論コストベースでは21.1%から35.9%の直接的な費用削減を実現することが可能である1。

## **結論**

自律型LLMエージェントのための共通Git操作スキルの提供は、毎回エージェントが即興でシェルスクリプトを書き、その複雑な生出力をパースするという、従来方式の非効率性と不安定性を克服するための根幹的な解決策である3。  
要求仕様において定義した「モデル非依存の均一インターフェース」および「セマンティックなトークン圧縮」は、エージェントによるGit操作の標準化に大きく寄与する3。詳細設計で示した正規表現によるスマートフィルタリング、差分情報の段階的分解（Recursive Dissection）、および超過データを裏側に逃がすCCRキャッシュ機構の組み合わせにより、エージェントが状況判断を誤ることのない「情報の完全性」を維持しながら、約75%から92%の圧倒的なトークン削減が達成可能となる3。  
さらに、プロンプトキャッシュのヒット率を高めるキャッシュアライナーの存在や、マルチターン特有の「期限切れの情報」を自律的にコンテキストから刈り取る設計は、エージェントがどれほど長期に及ぶ開発タスクを実行しても、その推論性能を劣化させないための堅牢な基盤を提供する2。本スキルの導入は、今後より長時間の推論を行う自動開発エージェントを構築する上で、必要不可欠なシステムコンポーネントになると結論付けられる20。

#### **引用文献**

> 1. Improving the Efficiency of LLM Agent Systems through Trajectory Reduction \- arXiv, [https://arxiv.org/html/2509.23586v1](https://arxiv.org/html/2509.23586v1)  
> 2. Reducing Cost of LLM Agents with Trajectory Reduction \- arXiv, [https://arxiv.org/html/2509.23586v2](https://arxiv.org/html/2509.23586v2)  
> 3. GitHub \- rtk-ai/rtk: CLI proxy that reduces LLM token consumption by 60-90% on common dev commands. Single Rust binary, zero dependencies, [https://github.com/rtk-ai/rtk](https://github.com/rtk-ai/rtk)  
> 4. RTK：AIコーディングエージェントのtokenを節約するCLIプロキシ \- KnightLi的博客, [https://knightli.com/ja/2026/05/27/rtk-ai-cli-proxy-token-savings/](https://knightli.com/ja/2026/05/27/rtk-ai-cli-proxy-token-savings/)  
> 5. LLM codeblock diff for merging algorithm : r/LocalLLaMA \- Reddit, [https://www.reddit.com/r/LocalLLaMA/comments/1f7y47i/llm\_codeblock\_diff\_for\_merging\_algorithm/](https://www.reddit.com/r/LocalLLaMA/comments/1f7y47i/llm_codeblock_diff_for_merging_algorithm/)  
> 6. GitHub Slashes Agent Workflow Token Spend up to 62% with Daily Audits and MCP Pruning, [https://www.infoq.com/news/2026/05/github-agentic-token-savings/](https://www.infoq.com/news/2026/05/github-agentic-token-savings/)  
> 7. Improving token efficiency in GitHub Agentic Workflows, [https://github.blog/ai-and-ml/github-copilot/improving-token-efficiency-in-github-agentic-workflows/](https://github.blog/ai-and-ml/github-copilot/improving-token-efficiency-in-github-agentic-workflows/)  
> 8. ModelContextProtocol tools入門 \- Zenn, [https://zenn.dev/jinjer\_techblog/articles/64062a1adc2a5b](https://zenn.dev/jinjer_techblog/articles/64062a1adc2a5b)  
> 9. Tool output compression for agents \- 60-70% token reduction on tool-heavy workloads (open source, works with local models) : r/LocalLLaMA \- Reddit, [https://www.reddit.com/r/LocalLLaMA/comments/1qbei13/tool\_output\_compression\_for\_agents\_6070\_token/](https://www.reddit.com/r/LocalLLaMA/comments/1qbei13/tool_output_compression_for_agents_6070_token/)  
> 10. GitHub \- headroomlabs-ai/headroom: Compress tool outputs, logs, files, and RAG chunks before they reach the LLM. 20% fewer tokens for coding agents, 60-95% fewer tokens for JSON, same answers. Library, proxy, MCP server., [https://github.com/headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom)  
> 11. トークン節約術: RTK (Rust Token Killer) を導入してみた \- Qiita, [https://qiita.com/kahibella/items/26b20f40c4c3e4cdd0c8](https://qiita.com/kahibella/items/26b20f40c4c3e4cdd0c8)  
> 12. Precision Dissection of Git Diffs for LLM Consumption | by Yehezkiel Dio Sinolungan, [https://medium.com/@yehezkieldio/precision-dissection-of-git-diffs-for-llm-consumption-7ce5d2ca5d47](https://medium.com/@yehezkieldio/precision-dissection-of-git-diffs-for-llm-consumption-7ce5d2ca5d47)  
> 13. Growth-Kinetics/DiffMem: Git Based Memory Storage for Conversational AI Agent \- GitHub, [https://github.com/Growth-Kinetics/DiffMem](https://github.com/Growth-Kinetics/DiffMem)  
> 14. Manage the Context of LLM-based Agents like Git \- arXiv, [https://arxiv.org/pdf/2508.00031](https://arxiv.org/pdf/2508.00031)  
> 15. Git Context Controller: Manage the Context of LLM-based Agents like Git \- arXiv, [https://arxiv.org/html/2508.00031v1](https://arxiv.org/html/2508.00031v1)  
> 16. Diff Parser: Breaking Down Code Changes for Review | CodeSignal Learn, [https://codesignal.com/learn/courses/ai-integration-and-analysis/lessons/diff-parser-breaking-down-code-changes-for-review](https://codesignal.com/learn/courses/ai-integration-and-analysis/lessons/diff-parser-breaking-down-code-changes-for-review)  
> 17. Build 30 for 30 Day 02: Git Diff Explainer | by Jason Dookeran | Medium, [https://jdookeran.medium.com/build-30-for-30-day-02-git-diff-explainer-115cbe62329e](https://jdookeran.medium.com/build-30-for-30-day-02-git-diff-explainer-115cbe62329e)  
> 18. The Token Efficiency Playbook: 10 Methods to Spend Less on LLM Inference, [https://builder.aws.com/content/3FRlppwY0rQsApCRxEksJP0s6hX/the-token-efficiency-playbook-10-methods-to-spend-less-on-llm-inference](https://builder.aws.com/content/3FRlppwY0rQsApCRxEksJP0s6hX/the-token-efficiency-playbook-10-methods-to-spend-less-on-llm-inference)  
> 19. gitdiffparser \- PyPI, [https://pypi.org/project/gitdiffparser/](https://pypi.org/project/gitdiffparser/)  
> 20. Context Compression for LLM Agents: A Survey of Methods, Failure Modes, and Evaluation, [https://www.preprints.org/manuscript/202605.2065](https://www.preprints.org/manuscript/202605.2065)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEYAAAAaCAYAAAAKYioIAAAC6klEQVR4Xu2XS6jNURTGP3nkmWckrwyIvJOBx+AWeRUKAxIDbyEhlJCSQnlEZOCGhEgMPMojj0zEQClGlNEdUEaUUvi+1l799/nfe67OcdTRf3/16567195r7b322uveAyQlJSUlJdWrlpIv5FfEV7I+nlRUtSHnyU8yI2crtHqSV+QjGVBqKrYmkm/kBmmXsxVay2C9ZVveUGR5f/lBpuVshZb3lw+kX85WaNVzf+lKrpDvqL6aZ5PPqOJ89d5fRpIX+Lu/lifJuvxga/of+st8ch0V3nakbuQ+Kjxfuf9flLBZ5B4ZH8YGkpWwDQ6FlfhiMpVcIydI9zBX6kP2kTtkLWlP2pJF5CZZTqYgO7BiquwvwS5reBjXbZ8hh2C+xoZxSf7mkgsB7dHHPc4RWMVV1D/L9ReVrw69m+wPYypFbVIH2ExmkvdkcrBfJPPC5yHkLhlGGshbWOJPk00wH/LtcfX7zjDWhdyCPW31mKdkD+yw8q84khItfztg6yeRNWH8LLI4B9H8fGWl22pC6fejT2RVsPclg2EVoxJUgMtkISyADqxE6WZl0wEewL5OyH6V7IKpI+kBS+BLZDenJHtfk+0NLHny1wt2wHx/kU+tkxRLe9Z3ug3kHKxiGshrtBynJlI1PYQ9Nz2LJ7CNSt6b1Lil0eRZmNefvEPzN61DKbmeSE+621q61bi/dCK3Yc9N0hpVlhIYK45TVX/5k1S2HkBl+hjWE+bAkqWkKXmSNqOSnU4WwG5ZyXKNInvDPEk2zVGlLIHdqJ6FS71qBMxnvEbJ1089E1WsPyvJ12h+uTg1kfeJ1bBNPycHYOU6Dnbj3my3k+NkC+lAtpJjsM0chSVTTVNVodJXD3gEa4yqQsXS7a8gG8lhWBxViN/2hDBHMQbBYjfC/PkaPcExyOKcQmmcmkll6odXrxCSGmHn8NmlpqnqcnlviaV1Km9JvpVEV9xbXHmfmh/bZeuNbF+u1uIkJSX9W/0GMjWMRYZilNQAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADUAAAAaCAYAAAAXHBSTAAACYklEQVR4Xu2XS8hNURiGX7nkmtyFUowUKaTIQFEYkFIiGRkgokz8zCUiIjIQSUoSSi5JKQOJgZmBKCMDAyNMFN6nb632tvzOf36XP7v2W0/n7PXttda3vsve50itWrVq1UrabD6YbzU+mh31m5qoQeai+WpWFrbGapx5bt6a6T+amquF5pO5boYUtsZqi6KX9pWGpir30xezrLA1Vrmf3pgpha2x+tf9NM08Nu/MrMLWrXaaz+ZQafiVBqKfeE08MKNLQ5cabm6qy9fNQPXTfvUjyr1ohnmqLjPd1/tptjlhbpn1iiAMNhvMDbPVLFVVtkPNJkVUj5upiijfNgfNeXNF4WTWCMUcyp85Y2vj2xX7HDP3zKhk66hO/bRYcZjxZpuifNjwjNmtOCCO5rkcCBs/uyaaF2aNIliv0jhzyBog1iMABAkROOYwfsesVqzNHn1mmgjTuPXfe+8VziMWfWLWpWt6AZaYZ6qekqdU9SLRfpTuI5sT0me9n3K5kwHE52uFPxw0Zwo/7iqylTPNYf9IZPClfq5hNqZ8cA4n2Tj34iX1Hs16PxEMnoRz0zVzjijWq4txqgD1q586ab4iU5PSNZsuMAdUlQ6OsRnZI0v0y65kQ/QTPXlNVcYpJ8ptkdmoyHReDzFnpuJQa9MYc+inFWZ5Gvst0R8nFdHikX9akb15ivrmb8k589AcNXMUjuIwB8TRHoWDZCZHmcNdMHsVZYb9qmKPPIeSW2Uumz3mrLlvDpvJ+gvKvVQXfTImfefwwwpb7iVEhssn1khVdsR3HiysVRfXeS57lPZWrf4XfQcj8G/JxQ2s1wAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAABK0lEQVR4Xu2TIUsEQRiGP/EMghcOBTnBIlfEZNAkBpFrNpt/wG6yXTFYDCIIFqM/QTAJtrsmiEFBLAqK+gME9XmdHZyd2V0sYtkHHg7m/e7b2dlvzGr+nHHs4jrO4nA+LmYIl7GPp7iReYY3uPBTmjKCu3hnaaGyI3zD+Sj7RgWH+IqLUebRa7zggbmd5tjEj+y3jBYO8AonwqCDD3iNk2EQ4RvcYzsMeviJO+FiATP4aFGDMTw3t/1Vv1iCctVdYNMvqpM66nB0SFXsm9tpL1z0DZL3ipg2NwfPOBcGOk2dalUDfbJtc0/fijJr4Am+41KUeTQXGiANkuYlQZOlgmNLC1bwCfdwNMpyaHRvzd0BP/+6C5fmmiSTV4Rum76Ebt8aTtkv/1jzn3wByukz0ukrHwsAAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAaCAYAAACzdqxAAAABTElEQVR4Xu2ULUsEURSGj2BQ0KKCQcNiM4pY/ACDRo27P8Bitqhti0EQwWwUsRgVRAz+CaNgUEwiiBoUP553zr3s3v1gdyyWeeBhhz2HM2feubtmBQWdmMVH/Ane4EjSkbKMX+a9+rzC4aSjgT18wHscb6hFNOAEX/AUe9NyMwN4hAf4htNpOaMH13Ebv3EjLbdmAg+xbP6IK2k5Y8p88BZ+4nxabs2q+SYz+G7N2/RjFcfwHG9xtL6hHVVcwkl8wp2kalYxr2vwneXMVy9MW2ibY/NMRQk3zQdpeO58+8xvch3UtYZpaMlbs+vc+QptqW1jhtpQMQjd+E/5RpSvcl7EXfMXJxSVznjX+erAK46I8tPJ0AAdsUiufOfwDAfrvtMZ1llWPPEFCj1Jx3wX8Nlq/w8fuBZq+tVdWu33v4+voS/2XuBQqBcU/Ae/emZGcKiQxL8AAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,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>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAWCAYAAAArdgcFAAABeUlEQVR4Xu3UPyhFYRjH8UcoIgal/CmSxWRQRDJZJAaZrMKoLEpJksnGIslgEam7yWBC8mdASZIBi8lokML3Oe/7uq9z7uncazLcX326533Pc55zz5/3iOSTT65pxAjqUYgStGLcbielApNYwyxq/J1deMeX5w39flFMGnCNMTF/pA/3aHcFbbjFHa4wL6Gzx6QI69i12y6L2HcDbb6S3pd1mvCC6dD8kJgrD/LX5r34lGjzATG3Nog2T2ETD3jGHEpdQUxck8TmZ2i24yqci3n6xa4oQ7RpYnNtUJbeF2RGzBvUGZr3MyVZNM8U96+0QVwSb4veggvcoNoriLtkP934kGjNT3N9n58k2lxvixYMenOVqEWBHdfhEcuuwGYCr7qhL/8qOryd2uQQB3Zbo1eoK9F/DnqSBZx6dfr8drBlx8ESPsISRnGJEzHfGpdy7IlZ2lrvok11flvM0t/Asfw+NjhjD4bRIuYDlm20Vl9nPVZ/czn2H+Yb4JxNZkByJNQAAAAASUVORK5CYII=>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAWCAYAAAArdgcFAAABFklEQVR4Xu3TMUuCURTG8RMWNIgNTWqguDk0BULh2NIghDj4BURoCVycnKIv0BgiOIQUzuHU1NBaY5OB4OSWg0Tm//jeWy+3QUXfQfCBH3qPl0de8YhssskySaLoDmckgkvcooao/8M0LvCEbzT9H85IAq8oYRdneEfGXtDyc5ygJ/OXb6OOtnlvc42O7zyNPs6HzF+eQh9VZ57H0JktXH6Ksfwvz+HHmS1cbksCKdfSwMorEmB5oD9LFl+yovI9xLBlznF0cWMvmJQxcGa/5XfyV2CzL94mjnBsZnrnCi/ifbFmBw9omfP0/6qbqauvj6M+8YZDcyeMR/FWW1feRkt1fi/e6jfwjAPfnaUSwhEK5lXPa5wJkNdD8U6nUeEAAAAASUVORK5CYII=>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAWCAYAAAChWZ5EAAACG0lEQVR4Xu2UO0gdURCGR0JAIRKDhSiKDyQhIChICBaKhRYWisSAYoLpbC0EX9WFJIUiYiOCjQ+wsEiRQkEsDNgoKUTwAUogBB9YiI0KKiH+/z1n7p49ulcIdt4fPnZ3ztmZ2TmzI5JSSikFygDtYAIMgVfh5aTiXr7Dd7tBbnhZ0kEHKLP3T0A+6NQNz8ES+AyegQqwDVp0QxJxzzdQDqrBOrgC75w9WWAN/PMY1g294Cd4oQboA9gBOY7NF9dWQB1Is7ZScAj2QIG18aPmwSb4BabAW7HvMCiDT9vNqjfgDDR5dleV4FyMU02UTmfFfGGDtTEB+vePJq7X4ERuJ6DOv3p2Vzw6ln9STBAVfTGBRvucNAENFJWAb79PWtFjCRqZCcyBETHHcAC+gyIuMktm6wf63wRawV/QI0FfMIFFu0YbYcPvcpHn9FAJFIpp3Bh46tgZMNNeVeyxC95EBYqyR4n9wE7vEvOf3yf1LyXgSG4H0g0Dnv0uaXAtMVUjZp5Qg+Aa1NtnKpEAz+eHGAecUir+2xwovKoYKE/CpWSpRyU8eKgvYspM8ePYF24CiSOgPoI/oNg+a5OsiglKZYMNcAmqrI3BY9bG95V98FtMdak20CdB4rz2g1P7HHc0DpZBs5jgWxKUkGKlFsR0LpuN0jL6I5a4k5X+x8TMjE9gRszs0UEVF7N6Cd6LOT+3ix9Crv9aCR/3I9YNKwxz0MSvSekAAAAASUVORK5CYII=>