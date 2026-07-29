# **GitHub CLIを基盤とする自律的AIエージェント統合システムの要求仕様・詳細設計構造化分析レポート**

## **1\. 開発エージェントにおけるGitHub CLI活用の技術的背景と課題分析**

ソフトウェア開発自動化の領域において、大規模言語モデル（LLM）をベースとした自律的AIエージェントの活用が急速に進んでいる1。自律的エージェントがコードの記述、テストの実行、デバッグ、プルリクエスト（PR）の作成からマージに至る一連の開発サイクルを自律的に遂行する中で、プラットフォーム（GitHub等）とのシームレスな通信経路の確保が必須の技術要件となっている3。  
これまで、エージェント環境におけるGitHubプラットフォーム操作には、Model Context Protocol（MCP）などの動的かつ汎用的なAPI統合スキーマが多く採用されてきた3。しかし、MCPサーバーを用いたステートレスな通信モデルには、重大なリソース上のボトルネックが存在する3。LLMへのAPIリクエストは原則としてステートレスであるため、エージェント実行ランタイムはすべてのターンにおいて、利用可能な全てのツール定義スキーマ（JSON形式等）をプロンプトに内包して送信しなければならない3。例えば、40個のツールを備えた標準的なGitHub MCPサーバーを運用する場合、1ターンごとに約10KBから15KBものスキーマ定義が入力コンテキストに自動追加され、エージェントが実際に使用するツールが数個のみであっても、未使用の38個のスキーマがすべてコンテキストのオーバーヘッドとして蓄積され続ける3。  
さらに、自律的エージェント特有の「成長し続ける軌跡（Trajectory Snowball）」問題がこのリソース消費を悪化させる1。マルチターンエージェントは、過去の思考プロセス、実行したコマンド、およびその出力をすべて累積的な文脈として持ち回るため、入力トークンの消費量は各ステップで雪だるま式に増加する1。ある統計分析によれば、Claude 4 Sonnetを用いた一般的な開発エージェントのセッションにおける総消費トークンのうち、実際にLLMが生成した出力トークンはわずか1%に過ぎず、残りの99%は累積した軌跡（軌道トークン）に費やされている1。  
この軌跡データには、人間の開発者の観点からは明らかに排除可能な「3大ノイズ（無駄）」が蔓延している1。

| 軌道内ノイズ分類 | 発生メカニズムと具体例 | 影響とコスト負担 |
| :---- | :---- | :---- |
| **不要情報（Useless Info）** | ディレクトリ走査時のキャッシュファイル（\_\_pycache\_\_ 等）やビルドツールが生成する冗長なディレクトリ移動ログ7。 | 不要なトークンが永続的にコンテキストへ蓄積され、モデルの注意力を低下させる7。 |
| **冗長情報（Redundant Info）** | ファイル編集ツール（str\_replace\_editor 等）呼出時、置換対象となるコードブロックが引数と応答結果の双方で重複して出現する現象7。 | 同一コード片の二重ロードを招き、コンテキストを不要に圧迫する7。 |
| **期限切れ情報（Expired Info）** | 特定のバグ原因究明のために grep コマンドで一覧取得した大量の関連ファイル候補など、ターゲットとなる不良箇所が特定された後は参照価値を失う一時データ7。 | 解決フェーズに移行した後も、初期の探索ログがコンテキスト予算を消費し続ける7。 |

コンテキスト窓における長大なテキストデータの蓄積は、APIコストの上昇を招くだけでなく、LLMが重要な情報を見落とす「Lost in the Middle（中央部での情報紛失）」現象を誘発し、エージェントのタスク達成能力そのものを著しく低下させる7。  
このような背景から、「LLMへの問い合わせは、行わないのが最も安価である」という根本的な効率化アプローチに立ち返り、プラットフォーム操作を決定論的かつ軽量なGitHub CLI（gh CLI）へと代替するシステム設計が極めて重要な意味を持つ3。gh CLIによる統合は、複雑なLLM推論を要する「データ取得プロセス」を、ローカルで実行可能な決定論的HTTPリクエストに変換し、不要なスキーマのインジェクションを完全に抑止する4。

## **2\. システム要求仕様定義（Requirements Specifications）**

AIエージェントシステムへの gh CLI統合を実用化するにあたり、クリアすべき機能・非機能および統合要件を以下の通り定義する。

### **機能要求仕様（Functional Requirements）**

開発プロセスを完全に自律化するため、システムは gh CLIを仲介役とし、GitHub上の全主要リソースに対する操作能力をエージェントに提供しなければならない4。

| 仕様ID | 要求項目 | 技術的詳細とカバー範囲 |
| :---- | :---- | :---- |
| **F-1-1** | プルリクエストのライフサイクル管理 | PRの一覧取得（gh pr list）、詳細ステータスおよびCIチェック結果の閲覧（gh pr view）、新規PR作成、レビュー追加、自動マージ処理5。 |
| **F-1-2** | 課題（Issue）の追跡と制御 | 課題の一覧検索（gh issue list）、課題の起票、進捗に応じたラベル・クローズ状態の動的制御5。 |
| **F-1-3** | ワークフロー（GitHub Actions）の監視 | 実行中のジョブステータスのリアルタイム監視（gh run list）、ビルドエラーログの取得と解析支援5。 |
| **F-1-4** | 高度な多目的検索の実行 | リポジトリ情報、特定のコードシンボル、コミットログ、Issue/PRの横断的なキーワード検索（gh search 系のサポート）9。 |
| **F-1-5** | 透過的なWeb API呼び出しのフォールバック | 独自拡張フィールドやラッパーが標準対応していないエンドポイントに対し、gh api コマンドを介して直接REST/GraphQLクエリを実行可能にする4。 |

### **非機能およびエージェント統合要求仕様（Non-Functional & Agent Integration Requirements）**

非機能要件では、コンテナ化されたエージェントサンドボックス内での高速性と安全性を両立させる必要がある5。また、エージェント特有の要件として、LLMへのコンテキスト注入時におけるトークン消費効率を能動的に最適化する仕組みが求められる5。

| 仕様ID | 要求項目 | 技術的詳細とカバー範囲 |
| :---- | :---- | :---- |
| **NF-2-1** | 低遅延・省リソース性能 | エージェントの毎ターンのレスポンスを阻害しないよう、CLIの起動および出力フィルタリングをミリ秒単位で処理する。ゼロ依存の静的リンク単一バイナリによる配布が望ましい5。 |
| **NF-2-2** | セキュアな認証隔離（信頼境界の維持） | エージェントプロセスに GITHUB\_TOKEN などの高権限秘密鍵を直接保持させないアーキテクチャ。中間プロキシによるヘッダ動的注入や、Squidプロキシを用いたハードな宛先許可リストによるインターネット統制を敷く3。 |
| **NF-2-3** | セマンティック圧縮能力 | コマンドの生のテキスト出力をそのままコンテキストに流さず、独自のセマンティックルールに基づき不要行を破棄し、トークン占有率を60%〜90%削減する5。 |
| **NF-2-4** | 自律監査・フィードバックループ | CIパイプライン等で動作するエージェント自身のトークン浪費傾向を能動的に監査し、異常なリソース消費を検知した場合は自律的に修正PRを起票する仕組みを提供する3。 |

## **3\. システムアーキテクチャおよび制御ポリシー設計**

システムは、エージェントランタイムをコアとし、認証情報を保持するローカルのシークレットストア（Vault）、透過的ネットワークゲートウェイ、およびコンテキスト最適化を司る監査用自律サブエージェントによって統合的に構成される3。

### **トークン消費最適化のための数学的モデル**

システムの運用時におけるトークンコストを管理・制御するため、評価指標となる有効トークン数（Effective Tokens: ![][image1]）およびその累積加重コスト（Weighted Effective Cost: ![][image2]）を、以下の数式モデルによって定義する3。出力トークンやキャッシュされた入力トークンの単価差異を反映し、実際の費用削減率に直結する定量評価を可能にしている3。  
![][image3]  
\[cite: 3\]  
各変数の定義は以下の通りである。

* ![][image4]: APIサーバー側でキャッシュにヒットしなかった、通常の入力プロンプトトークン数3。  
* ![][image5]: モデルによって生成された出力トークン数。APIの価格体系に基づき、入力に比して約4倍の重み（![][image6]）を加算する3。  
* ![][image7]: APIプロバイダ（AnthropicやOpenAI等）のプロンプトキャッシュから高速に読み出された入力トークン数。約10分の1のコスト（![][image8]）として優遇評価される3。

最終的なプロジェクト全体の加重コスト ![][image2] は、選択したLLMモデルファミリーの価格Tierに応じたモデル乗数 ![][image9] を用いて計算される3。  
![][image10]  
\[cite: 3\]  
モデル乗数 ![][image9] は、検証対象とするモデル階層ごとに、以下の表の通り規定される3。

| モデルファミリー例 | 代表的なモデル名 | モデル乗数 (Mmodel​) |
| :---- | :---- | :---- |
| **Haiku Tier** (軽量高速型) | Claude 3.5 Haiku / Llama 3.2 3B3 | 0.253 |
| **Sonnet Tier** (実用能力型) | Claude 3.5 Sonnet / GPT-4o | 1.003 |
| **Opus Tier** (超長考・最高性能型) | Claude 3 Opus / o1 | 5.003 |

本システムでは、この ![][image1] 指標をシステムプロンプトの更新やプロキシフィルタの動作閾値としてリアルタイムにフィードバックし、無駄なツールトークンの発生を防ぐ自律フィードバック制御を行う3。

### **自律監査ループ（Auditor-Optimiser Loop）**

継続的なトークン消費効率化のため、システムは人間の手を介さずに自律的に動作する2つのエージェントループを包含する3。

\[Agent Runs Workflow in CI\]  
              |  
              | Writes normalised data to: token-usage.jsonl  
              v  
  \+--------------------------------------------+  
  |    Daily Token Usage Auditor (Agent 1\)     | \<--- Flag anomalies and expensive runs  
  \+--------------------+-----------------------+  
                       |  
                       | Flagged Workflows & Logs  
                       v  
  \+--------------------------------------------+  
  |       Daily Token Optimiser (Agent 2\)      | \<--- Analyse logs and propose fixes  
  \+--------------------+-----------------------+  
                       |  
                       | Proposes specific code / tool-set improvements  
                       v  
\[Opens GitHub Issue & Automated Pull Request\]

> 1. **Daily Token Usage Auditor (トークン利用監査エージェント)**: 毎日のCIビルドや開発セッションで書き出される標準化ログファイル（token-usage.jsonl）を自動巡回する3。このログには、Claude CLI、Copilot CLI、Codex CLIなど、使用されたモデルの別を問わず、入力、出力、およびキャッシュヒットトークン数が正規化されたフォーマットで記録される3。監査エージェントはこれらを統合的に集計し、あらかじめ設定された移動平均閾値を超える異常値（アノマリー）を示した実行ジョブ、あるいは絶対的消費額の大きいトップ10のジョブを検出・リストアップする3。  
> 2. **Daily Token Optimiser (トークン最適化自動実行エージェント)**: 監査エージェントが特定のワークフローに警告フラグを付与すると、最適化エージェントが直ちに起動する3。対象となったワークフローのソースコード、および直近の実行ログを読み込んで問題点（代表的な例として「未使用のMCPツール定義がプロンプトに含まれたままになっている不具合」等）を特定する3。特定後、最適化エージェントは自動的にGitHub Issueを起票し、修正箇所をピンポイントで示したPR（プルリクエスト）を自動作成する3。

### **セッションコンテキストの構造化管理（Git-Context-Controller: GCC方式）**

単純な過去ログの切り捨て（Truncation）は、エージェントが過去の決定や複雑な設計意図を忘却するという致命的なエラーを引き起こす17。これを防ぐため、本設計はGitのバージョン管理セマンティクスを取り入れたコンテキストコントローラ（GCC）をコンポーネントとして採用する17。  
エージェントの思考ステップ、作業計画、およびこれまでの実行履歴は、単純なテキストストリームではなく、ローカルの永続化ディレクトリ（.GCC/）以下に構造化されたMarkdownドキュメントとして保存される17。エージェントは、コントローラが提供する以下の「コンテキスト制御API」を用いて情報の解像度を動的に調整する17。

                 \+--------------------------------------+  
                 |     Git-Context-Controller (GCC)     |  
                 \+--------------------------------------+  
                                   |  
    \+-----------------+------------+------------+-----------------+  
    |                 |                         |                 |  
    v                 v                         v                 v  
\[COMMIT\]           \[BRANCH\]                  \[MERGE\]          \[CONTEXT\]  
Saves state       Explores alternative       Combines paths   Retrieves history  
(main.md)         reasoning branches         of reasoning     at multi-resolution

* **COMMIT**: 現時点までの意味ある進捗や仮説、決定事項をコミット履歴のように保存し、main.md 上のロードマップを更新する17。  
* **BRANCH**: 代替のコード解決策やデバッグ方針を試すために、コンテキストの別ラインを分岐して検証する17。  
* **MERGE**: 分岐した別エージェントや検証の成果から、最も確度の高い推論プロセスのみを主脈コンテキストに融合する17。  
* **CONTEXT**: 過去の試行錯誤を要約レベルから低解像度な要点（Todoリスト、コミットサマリー）、さらには高解像度なログまで、必要な粒度を選択して引き出す17。

## **4\. コンポーネントおよびフィルタリング処理の詳細設計（Detailed Design）**

システムは、エージェントと実際のGitHubプラットフォームAPIの間にプロキシレイヤーを挿入し、コマンド出力をセマンティックルールに基づいてインターセプトして動的変換する5。

### **透過的認証隔離プロキシ（Credential Isolation Proxy）**

コンテナ化されたエージェントサンドボックス環境における、gh CLIの認証を処理するシーケンスを以下に詳述する4。

\[Agent in Docker Sandbox\]        \[Host Vault / Agent Handler\]           \[Squid Proxy (egress)\]           \[api.github.com\]  
          |                                   |                                    |                             |  
          |-- (1) gh pr list \----------------\>|                                    |                             |  
          |                                   |-- (2) Check Credentials existence \-|                             |  
          |                                   |-- (3) User Approval Dialog \-------\>|                             |  
          |                                   |   (Host-side popup approved)       |                             |  
          |\<-- (4) Mount Temp Env Verification|                                    |                             |  
          |                                                                        |                             |  
          |-- (5) Exec HTTPS request to api.github.com \---------------------------\>|                             |  
          |                                                                        |-- (6) Inject GITHUB\_TOKEN \-\>|  
          |                                                                        |\<-- (7) Return raw JSON \-----|  
          |\<-- (8) Compacted Text/JSON Response \-----------------------------------|                             |

> 1. エージェントがサンドボックス内で gh pr list コマンドを実行する5。このサンドボックスは \--security-opt=no-new-privileges:true を適用され、すべてのLinuxケーパビリティ（--cap-drop=ALL）が排除されている12。  
> 2. エージェントが実行した通信は、内部専用ネットワークのデフォルトゲートウェイを介し、透過的フォワードプロキシ（Squid）へとルーティングされる12。  
> 3. プロキシはホスト側の認証情報管理Vaultと対話する。Vaultは事前に認証トークン（GITHUB\_TOKEN）を保持しており、初回接続や重要操作時にホスト側のポップアップ承認を求めた後、リクエストに Authorization: token \<SECRET\> ヘッダを自動的に注入してGitHubのグローバルAPIに要求を中継する3。  
> 4. これにより、サンドボックス内のエージェントがファイルシステム上から直接トークンを窃取するリスクを完全に遮断する3。

### **インターセプトフックと自動リライトエンジン**

エージェントがBash経由で命令を発行した際、プロキシツール（rtk や tokf）はコマンド文字列をパースし、事前定義された対応コマンドである場合に呼び出し先を自動的に書き換える5。

#### **コマンド判定マトリクスとマッチング詳細仕様**

エージェントが頻繁に使用するコマンドに対する、リライト挙動、およびプロキシフックにおける重要なシステムバグ回避の実装詳細を以下の表に示す9。

| オリジナルの発行コマンド | フックによるリライト結果 | 処理パターン | 詳細設計上の注意点とバグ回避ロジック |
| :---- | :---- | :---- | :---- |
| gh pr list | rtk gh pr list | 自動書き換え（リライト）9 | API応答を受け取り、行圧縮エンジンへ流す5。 |
| gh issue view 12 | rtk gh issue view 12 | 自動書き換え（リライト）9 | コメント本文のアスキーアートや無駄な改行を排除。 |
| gh api repos/foo/bar | rtk gh api repos/foo/bar | 自動書き換え（リライト）9 | 生のJSONからネストされた空フィールドを削除5。 |
| gh search repos \--limit 5 | rtk gh search repos \--limit 5 | **直接実行（パススルー）または不適合による未変換** \[cite: 9\] | **【重要設計バグの回避】** 既存製品（rtk 0.37.2時点）では、フック登録用Claude PreToolUseのマッチャーに search が登録されておらず、エージェントが実行時に生出力を受け取り、トークン暴走を起こす欠陥があった9。詳細設計においては、マッチャーの正規表現許可リストに search サブコマンドを明示的に包含し、rtk gh search へ正しく強制リライトさせるフックパッチを適用する必要がある9。 |

### **４大スマート圧縮処理アルゴリズムの実装仕様**

抽出されたデータストリームは、以下の4つの処理パイプラインを順次通過して圧縮される5。

\[Raw CLI Output Stream\]  
          |  
          v  
\[1. Smart Filtering\] \-------------\> Strips comments, ANSI escapes, empty lines  
          |  
          v  
\[2. Smart Grouping\] \--------------\> Groups files by directory, errors by class  
          |  
          v  
\[3. Smart Truncation\] \------------\> Applies Recursive Dissection Strategy  
          |  
          v  
\[4. Deduplication & Merging\] \-----\> Collapses repeating lines into run counts  
          |  
          v  
\[Compacted Token Stream\]

#### **1\. スマートフィルタリング（Smart Filtering）**

* **処理目標**: 実質的な変更内容と関係のない、装飾的、または定形テキストの徹底排除5。  
* **処理内容**: ANSIカラーコードの除去、マークダウン装飾ブロックの一部平坦化、空行および開発コメントの除去5。  
* **実装例（疑似コード）**:  
  Python  
  \# Ensure no citations inside code blocks  
  def smart\_filter(raw\_output: str) \-\> str:  
      \# 1\. Remove ANSI escape codes  
      clean \= re.sub(r'\\x1B(?:\[@-Z\\\\-\_\]|\\\[\[0-?\]\*\[ \-/\]\*\[@-\~\])', '', raw\_output)  
      \# 2\. Strip comment lines in command blocks  
      clean \= "\\n".join(\[line for line in clean.splitlines() if not line.strip().startswith("\#")\])  
      \# 3\. Suppress double empty lines to single  
      clean \= re.sub(r'\\n\\s\*\\n', '\\n', clean)  
      return clean.strip()

#### **2\. スマートグループ化（Smart Grouping）**

* **処理目標**: 構造化されたスキーマによるデータの集約5。  
* **処理内容**: PRの一覧やファイルの追加一覧を、階層的なディレクトリパス、あるいはエラーレベルごとにソートし、マークダウンのコンパクトなテーブルまたはインデント階層へと再配置する5。

#### **3\. スマートトランケーション（Smart Truncation / Recursive Dissection）**

* **処理目標**: コンテキスト上限（例：500行、またはトークンリミット）を考慮した、情報密度（エントロピー）重視の差分切り詰め8。  
* **差分パーサ構造体定義（JSON/データクラス構成）**: 統一差分（Unified Diff）を以下のデータ構造へと厳密に分解する21。  
  JSON  
  {  
    "file\_path": "src/core/api.rs",  
    "status": "modified",  
    "hunks": \[  
      {  
        "old\_start": 102,  
        "old\_lines": 7,  
        "new\_start": 102,  
        "new\_lines": 9,  
        "lines": \[  
          {"type": "context", "content": "fn fetch\_data() {"},  
          {"type": "removed", "content": "-   let url \= \\"http://legacy.api\\";"},  
          {"type": "added", "content": "+   let url \= \\"https://secure.api\\";"},  
          {"type": "context", "content": "    return http::get(url);"}  
        \]  
      }  
    \]  
  }

* **再帰的分解ポリシーの実行手順**:  
  * **Level 1**: 各ファイルのヘッダメタデータを、そのファイルを識別可能な最小行数に切り詰める8。  
  * **Level 2**: 変更行を包み込む「文脈行（Context Lines）」を前後のコード定義境界を跨がない最小限（標準の3行から1行へ）まで削り、同一ハンク内の実変更箇所のみをタイトにパッキングする8。  
  * **Level 3**: 変更されたファイル種別が設定系や依存管理（例：package-lock.json、yarn.lock、Cargo.lock）である場合、中身の差分をすべてスキップし、「Cargo.lockが変更されました（+120行, \-80行）」といったセマンティック・メタ要約のみに置換する8。

#### **4\. 重複排除とマージ（Deduplication & Merging）**

* **処理目標**: ループ処理などで発生する、繰り返し実行された無変化状態の圧縮5。  
* **処理内容**: 同一メッセージが連続して出現した場合、それらをマージし、「(x 128 times)」などの行末カウンタ表記へと折りたたむ5。

### **代表的な実装アプローチの技術比較：rtk vs tokf**

現在、自律型エージェント開発コミュニティにおいて導入が進む2つのCLIプロキシエンジンの設計思想、および具体的な実装方式の差異を以下にまとめる。

| 評価軸 | rtk-ai/rtk\[cite: 5, 14\] | tokf\[cite: 20\] |
| :---- | :---- | :---- |
| **主要開発言語** | Rust (高性能・ゼロ依存)5 | Rust20 |
| **フィルター設定管理** | コンパイル済みの静的ビルトインルールによる最適化（高速性能重視）5 | **TOMLベースの外部設定駆動型**（カスタマイズ性重視）20 |
| **最大の特徴** | 100種類以上の主要開発コマンドの出力を自動網羅。Claude Codeへのグローバルフックイン（PreToolUse）を自動完了可能10。 | ライブラリとしての再利用を許容。ユーザーがプロジェクト固有のフィルタをTOMLで拡張可能20。 |
| **拡張の平易性** | Rustコードベースの書き換えと再コンパイルを必要とする。 | TOMLファイルの書き換えのみで独自パーサをプラグイン可能20。 |

## **5\. 性能検証および実証データの分析評価**

本システム設計を実プロダクションのCI/CD環境、およびコード変更自動対応エージェント（Auto-Triage / Security Guard 等）へ統合した際のトークン削減率、ならびにコスト効率を評価した結果を以下に示す3。

### **実証対象ワークフローにおけるトークン（ET）削減成果**

以下の表は、実際の開発現場でエージェントを連続稼働させ、gh CLIによる情報調達の代替、および動的フィルタリングプロキシを適用した前後での「有効トークン（ET）」の推移を計測した結果である3。

| 検証対象エージェントワークフロー | 実機での計測ラン回数 | 標準時ET（圧縮なし） | 最適化適用後ET | 実質削減率（%） |
| :---- | :---- | :---- | :---- | :---- |
| **Auto-Triage Issues** (課題の重要度・対応者の自動仕分け)3 | 1093 | 1.00 (基準値)1 | 0.38 | **62.0% 削減** \[cite: 3\] |
| **Smoke Claude** (Claudeベースの自動スモークテスト) | N/A | 1.00 (基準値) | 0.41 | **59.0% 削減** \[cite: 3\] |
| **Security Guard** (自動脆弱性スキャンおよび対応) | N/A | 1.00 (基準値) | 0.57 | **43.0% 削減** \[cite: 3\] |
| **Daily Community Attribution** (毎日のオープンソース貢献帰属評価) | N/A | 1.00 (基準値) | 0.63 | **37.0% 削減** \[cite: 3\] |
| **Contribution Check** (PRにおける寄稿ルールの遵守検証)3 | N/A | 1.00 (基準値) | 1.05 | **5.0% 増加** (※特記事項)3 |

### **実証値に対する詳細な技術的考察**

上記の実証結果より、本システム設計に基づくデータ調達の gh CLI化およびコンテキスト圧縮は、殆どの実用ワークフローにおいてETを約37%から62%削減するという極めて優れた費用対効果をもたらすことが示された3。この現象の背後にある技術的因果関係は、以下のように体系的に整理される。

#### **1\. トークン削減がもたらすエージェント推論精度の向上（SNR比の改善）**

コンテキスト窓内の不要情報（ビルド移動ログやアスキーアートなど）がスマートフィルタリング等で徹底的に削ぎ落とされることにより、LLMのアテンションヘッドが、コード編集に必要な真にクリティカルな変更行（PR Diff等）に正しく集中できるようになる7。結果として、コンテキスト縮小を施してもエージェントの処理成功率は低下せず、むしろ「Lost in the Middle」に起因するデバッグ失敗が抑制されるという副次的効果が観察された7。

#### **2\. 例外事例（Contribution CheckワークフローにおけるET増加）のメカニズム**

「Contribution Check」ワークフローにおいてのみ、最適化を施したにもかかわらずETが5%増加するという逆転現象が発生した3。この増加原因の調査によれば、本システムのバグやフィルタ最適化の破綻ではなく、「検証対象のプルリクエスト自体のサイズが、最適化評価期間中に本質的に大規模化した」という、外部的なワークロードのシフトが主因であると特定された3。実質的に評価すべきコード量（Diffデータそのもの）が飛躍的に増大したために、削減効果を上回る入力トークンが流入した格好であるが、これは本システムの動作安定性やロバストネスを否定するものではなく、むしろエージェントが情報ロスを最小限に抑えつつ適切に大規模なPRを処理できたことを示している3。

## **6\. 実用化に向けた統合的提言**

本システムの調査設計、および実証結果に基づき、企業および開発プロジェクトにおいてエージェント指向のGitHub操作インフラを構築するための重要な技術的推奨事項を提示する。

### **推奨1: 「取得はCLI、変更はコミット」という疎結合統制**

MCPツールの直接的な利用は極力避け、データ取得を gh CLI による決定論的ローカル実行へ統一することが、1ターンあたり10KB超のスキーマオーバーヘッドを排除するための唯一最大の手段である3。エージェントに自律実行権限（Bash ツールなど）を与えた上で、その内部呼び出しを透過的にインターセプトするプロキシ（rtk や tokf）を常時監視エージェントとして配置すべきである5。

### **推奨2: ポートフォリオレベルでの「読み書きの集約化（重複排除）」**

「最もコストが安いLLM呼び出しは、実行しない呼び出しである」という原則を徹底するため、個々のエージェントレベルのみならず、リポジトリ単位の「ポートフォリオレベルでの最適化分析」を計画に組み込むことが推奨される3。具体的には、同一リポジトリ内の別個のCIジョブが、同一のPR Diffや共通の中間成果物（コミット履歴等）を何度も重複して独立にロードするのを防ぐため、事前に共通キャッシュを共有ディレクトリに退避（事前バッチダウンロード）し、エージェントはローカルのキャッシュのみを順次読みに行くパイプライン設計を標準化することが有効である3。

### **推奨3: 強固なネットワーク境界隔離（Egress Control）**

エージェントが自律的に外部のGitHub APIを操作する際、プロキシの背後にあるシークレット情報へのアクセス制限が不十分であると、不正なコードが実行された際に GITHUB\_TOKEN が第三者の外部サーバーに流出する致命的なインシデントのリスクが生じる3。これを防ぐため、サンドボックス環境にはハードな送信先許可リスト（例：Squid等による api.github.com および github.com のHTTPS宛先隔離）を厳格に適用し、環境変数やファイルシステムを介さず「プロキシのパケットフィルタリング通過時にのみ動的にヘッダを差し替える」セキュリティ詳細設計を標準アーキテクチャとして採用することを強く提言する3。

#### **引用文献**

> 1. Improving the Efficiency of LLM Agent Systems through Trajectory Reduction \- arXiv, [https://arxiv.org/html/2509.23586v1](https://arxiv.org/html/2509.23586v1)  
> 2. Context Compression for LLM Agents: A Survey of Methods, Failure Modes, and Evaluation, [https://www.preprints.org/manuscript/202605.2065](https://www.preprints.org/manuscript/202605.2065)  
> 3. GitHub Slashes Agent Workflow Token Spend up to 62% with Daily Audits and MCP Pruning, [https://www.infoq.com/news/2026/05/github-agentic-token-savings/](https://www.infoq.com/news/2026/05/github-agentic-token-savings/)  
> 4. Improving token efficiency in GitHub Agentic Workflows, [https://github.blog/ai-and-ml/github-copilot/improving-token-efficiency-in-github-agentic-workflows/](https://github.blog/ai-and-ml/github-copilot/improving-token-efficiency-in-github-agentic-workflows/)  
> 5. GitHub \- rtk-ai/rtk: CLI proxy that reduces LLM token consumption by 60-90% on common dev commands. Single Rust binary, zero dependencies, [https://github.com/rtk-ai/rtk](https://github.com/rtk-ai/rtk)  
> 6. ModelContextProtocol tools入門 \- Zenn, [https://zenn.dev/jinjer\_techblog/articles/64062a1adc2a5b](https://zenn.dev/jinjer_techblog/articles/64062a1adc2a5b)  
> 7. Reducing Cost of LLM Agents with Trajectory Reduction \- arXiv, [https://arxiv.org/html/2509.23586v2](https://arxiv.org/html/2509.23586v2)  
> 8. Precision Dissection of Git Diffs for LLM Consumption | by Yehezkiel Dio Sinolungan, [https://medium.com/@yehezkieldio/precision-dissection-of-git-diffs-for-llm-consumption-7ce5d2ca5d47](https://medium.com/@yehezkieldio/precision-dissection-of-git-diffs-for-llm-consumption-7ce5d2ca5d47)  
> 9. \`gh search\` subcommand still unhandled by hook in 0.37.2 — appears related to \#446 · Issue \#1484 · rtk-ai/rtk \- GitHub, [https://github.com/rtk-ai/rtk/issues/1484](https://github.com/rtk-ai/rtk/issues/1484)  
> 10. rtk \- AI Agents on GitHub (71.9k ) | SkillsLLM, [https://skillsllm.com/skill/rtk](https://skillsllm.com/skill/rtk)  
> 11. A Thorough Explanation of the RTK CLI That Reduces Claude Code, [https://note.com/kudoucraft/n/nba79d716dc8c?hl=en](https://note.com/kudoucraft/n/nba79d716dc8c?hl=en)  
> 12. exitbox command \- github.com/cloud-exit/exitbox \- Go Packages, [https://pkg.go.dev/github.com/cloud-exit/exitbox](https://pkg.go.dev/github.com/cloud-exit/exitbox)  
> 13. RTK：AIコーディングエージェントのtokenを節約するCLIプロキシ \- KnightLi的博客, [https://knightli.com/ja/2026/05/27/rtk-ai-cli-proxy-token-savings/](https://knightli.com/ja/2026/05/27/rtk-ai-cli-proxy-token-savings/)  
> 14. RTK Complete Guide: Rust-Powered LLM Token Compression Tool That Saves 60-90% on Costs | Dashen Tech, [https://dashen-tech.com/en/dev-tools/rtk-token-killer-guide-2026/](https://dashen-tech.com/en/dev-tools/rtk-token-killer-guide-2026/)  
> 15. The Token Efficiency Playbook: 10 Methods to Spend Less on LLM Inference, [https://builder.aws.com/content/3FRlppwY0rQsApCRxEksJP0s6hX/the-token-efficiency-playbook-10-methods-to-spend-less-on-llm-inference](https://builder.aws.com/content/3FRlppwY0rQsApCRxEksJP0s6hX/the-token-efficiency-playbook-10-methods-to-spend-less-on-llm-inference)  
> 16. Build 30 for 30 Day 02: Git Diff Explainer | by Jason Dookeran | Medium, [https://jdookeran.medium.com/build-30-for-30-day-02-git-diff-explainer-115cbe62329e](https://jdookeran.medium.com/build-30-for-30-day-02-git-diff-explainer-115cbe62329e)  
> 17. Manage the Context of LLM-based Agents like Git \- arXiv, [https://arxiv.org/pdf/2508.00031](https://arxiv.org/pdf/2508.00031)  
> 18. Git Context Controller: Manage the Context of LLM-based Agents like Git \- arXiv, [https://arxiv.org/html/2508.00031v1](https://arxiv.org/html/2508.00031v1)  
> 19. トークン節約術: RTK (Rust Token Killer) を導入してみた \- Qiita, [https://qiita.com/kahibella/items/26b20f40c4c3e4cdd0c8](https://qiita.com/kahibella/items/26b20f40c4c3e4cdd0c8)  
> 20. TOKF — Rust utility // Lib.rs, [https://lib.rs/crates/tokf](https://lib.rs/crates/tokf)  
> 21. gitdiffparser \- PyPI, [https://pypi.org/project/gitdiffparser/](https://pypi.org/project/gitdiffparser/)  
> 22. Diff Parser: Breaking Down Code Changes for Review | CodeSignal Learn, [https://codesignal.com/learn/courses/ai-integration-and-analysis/lessons/diff-parser-breaking-down-code-changes-for-review](https://codesignal.com/learn/courses/ai-integration-and-analysis/lessons/diff-parser-breaking-down-code-changes-for-review)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAAAaCAYAAACgoey0AAABbklEQVR4Xu2UzSpFURSAl1CEgRSJ8jMwJTJQSsmAmUgpBkYGZkx4AQ/gZ6KUZEQewDsoUyOFZEAZiIn/b9l737vvuXs7Z8BE56uv21r7rHP3bq19RHJy/jsT+JnRFRzFC7zO6JiksI+vOJzIV2A/XuE0buMhdto1ZRc/cNzGlTiClzhoc0Ea8VTMg22lSwX05TN4hM1ePlZbjwfY7uXK6MVHPMYqm9PfPqy28QYu4rKNHaFaRTe0iQ1erow5MT1c9XK6ez1lnY2ncAF73AOWUK3SJGajrh1B9A/ecBJbsQN3cN1/KILWhmYjFdejd7wRM4l3Nk6byFh/MzGAz1LaI+2LDlG3jXVKQ70K1WbG9UjvqKMFt7DGxrO4VFwuEOtvKtr4Pfm5R+5adCXyWWqjuB7pl0hPGWJezOmT0/nr/XXoNVrDexxKrCk/1UbRab2V4jfYn2j1xVs7wVpT9n2Hz/DBW1ef8FzMZnJycv6eLw8ZZL3QkSu1AAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAABFUlEQVR4Xu3TvUtCURjH8SciKBIiBDEolGrR/gMhEHFwDGpvdbWpQqLFsaHJJaLa+gNCaJKCHPoPcgqi9pAGA+v7cM/15eH4sgQN/uADh/Oce+49L1dkmj9PBFnsIYVZ17+IVdf2Jo0GWrjFAW5wjy3UkO+O7sscymjjEAuDZdnGJ97E8wX6cBXf2DW1MPO4c7Q9kCJ+cIQZU+vPNY5t5ybe0cSaqdlciGf9pxK8vWL6fVmSYLnd6FHV0RHPzJNkBa/4wLqpTZRwAqXtUdGNztjOZTzL+AmiuETMFjRnEuxBwRZc9Fj1Ng67H5LACx4QNzW9jScoyej7IUk84QtX2Mc5HpGTMQ+H0UFJ7Dgb0vsDp/m3+QWDxin9EMHjJAAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFIAAAAaCAYAAAAkJwuaAAADT0lEQVR4Xu2YWahOURTHl8xT5ikyFSVlyBAipZuhUIgIuYZIpnhRoi7yIHkwRSghs3hQ5nIN5UFJHpBS8uLNg3hS+P9a+3T2Pbr3++693Qfsf/369rf32eesvc5a65x9zJKSkpKSkpL+Lk0TH8SnMqnwaUmxmomj4ooYGP6j0+KnmBn+NxdTxUcxLvQlReolroqeUV8X8cLcaX2j/g7ivOgX9SUFkaZbC30jxVdxXbSI+nHwYdEx6ksKWiiGFvqWil9ie6G/m1hrefonlRD18YeYXBxIKl+11cekemqM+G5/1sdYI8Ri+3dTnGfEe/HUGvE8qK0+xlpvXiv/Za0zf7A2SETYGUv1kUwkIwmqBqlUfWwvdotTolPom2P+HjpcrBF3RKWVTvse4pDYZF4qeMBdsJrvqC3NS8hNccx8w5DN2yLmi4tiovniyZITYojYYW7L9DDOhoNz9LZcXOugOCJmWL7m7uKRGBb+11ul6uM8McrcQIzjwqvNjb4nuoo+ojr81qVlYop5LVpg7njKSVZScCILXxLG2E1xw1aZz3tj7iScXCVGi9nmN+O4aGu+ns/mDkcHxLbQ5vjH5o7Foe8sz0J+GSOwyhbvkC/FF/PamPFNvDU3JhN3eoJ4YH4RHNdf3BJzwzEc/8z8rtYlzsX28775jikrK9QmRCQSFYwhzvtKTLKa88gMnM7OjLVw7cxmbML5BAXQpo/2JbExHEfkPTff5aFG1cdyVRXIRFTydBsc/mNcuUYQfftCm0VUW55OZ6MxRL2qNndePC8WDsxuMuKYLMIHmTuZX7LlteXfDIoOb1R9LEdEGcYQlRvM04c0uG2+QKBN6m0Ox9emOEJQthhKxyLzmlkZxrjONfMS0MY8A2aFsVgsnqgmurGFqK2IxojC8WK55eWHY/loQ8qvNL+RZAKRT9lqErFFfCj2mjsLYUBVaGM8xu4yL951iQjEYCIE4chz5hFEuo4Vd8UKc+ewlWXRxXmxTpqXBDRAPLH8AUL/ZfOHJetgDTvF/tDPNfjm0FncEHvMA6bJRD3i6Z2pVejLxOe2dqFNkcepRXBOa6t5HsQ85meizaLjPpxZnJcpns9x2BaLl+v4XJwns502c1BxjUlJSf+nfgMiuJnf8QpLRAAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACEAAAAaCAYAAAA5WTUBAAABvUlEQVR4Xu2UzStFQRjGH6HkI/mI5HOlrJAsSCkRFjZiZSdRdhTKSlkqReyUhSzIEoliYakkJSslf4CFWCk8T++c7nHcr9zjZnGf+nVn3plzZ+adZ14go4wyiq8e8kCekqTXPgtPWWSD7JEG15e2yAcZcP1s0k0eSbuLhaZKsk8qfLEScgVbsNoXLyQ7pMYXC0VK7Uwg1kxeyAHJ8cW1uXVS5IuFolHSGIiNkU+yEIiXkUlEruxPJT+8k67gQLoUyw9pVRt5w08/hKF82CtLqFh+SFXF5AR2yLiS4bbxN37Qi7sk5cGBoJLxgzaqAqZ6IVpdrJ8ckxY3T7VkHFZb5sgprNqukVo3J6oS+UGLzZNF2N1qIaVYWRtx8SU3dwpWUzyprVhUqUZck2eYFzxeyT2+32EHuUUkS1XkhvSROlgmtCFtdpcMu3nK8DlCKvcyqz9LWvAOtilt9gy2oO79gjS5efpVP6EfktEsWXFtnXYVdj1qD8FOr7ZOrJN3kkHYi9NYLpmGvZRfq54cwkq3DKZN6Y+9sSMyQTZhL2EZ5htdl7Ikz8jIKUsnLUVkcb8U806Z5/BUgOjfZPS/9AVhM1F+Pw0ZHwAAAABJRU5ErkJggg==>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAF8AAAAaCAYAAADR2YAqAAADp0lEQVR4Xu2YW4hNURzGP7lESC6RIuOeRMK4hRc8eHAdyqB4QymXF5FQiFwKJULkBbkkD0LEKYWiSKGUxItS3lCUy/fNf6/OPmvOOmefOsycaf3qa2avtc/ea3/rv/7rvzcQiUQikUgk0tbpQz2m/qT0iZpADaCee31vqRFNvwRWen03qK5JXy3TjtpIrfU7AnShllOnqAPUyMLu8myBGbje7yDbYH2L/Q4ylrpP1Xnttcxk6hvMk3L0oO5Su6lu1DjqNdWQPqkcK2AGF7uhM1/npFGEbKfmeO21jMxUMIW88NE5T6meqTb59Ibql2oryTzYDWV0mjrqHYoPZjRsmXX02msVBdNm6iCyRb4Ml/HnvfZ66is132sPMpv6jcILaTB7qCNobn4Hah9sAtoKSjeHqKnIZv4o6guam6/9Ur/f67UHcT9IX0ht+2G5Xuan+2ZQW2ET1BZQutGGWYe8F+XML+ZZqfYg7gf3YBWLUslRaliqz11MG8sJamBy/D9ppD5WoGewZyiFAmgTtTQ5zmq+S9W+yb5fZelPfaByMHO1iarcEv7EaENZk/RVAz18S5aok6jDyO9dWc2fiyqbrw1EkXKW6pv0udyWo4ZSx2ETVC2UY2+iutfMiu55EoWlclbzQyaH2oO4nVsTsBP5JSjcxDykdqD6paUqjGN+Y4DOsPFklcq9UtXYGOolClPVZ1hEq2LRsYqRYgyBvZD6Jjvz/coxiCIgB6t4LsHe2hzOfA3oIsIPo/Zl1HXY6qiDXUeDOA3b1MQsambSr33lPezemoROyTkhBlFLKtACqlfTL7MTinw9n+7vnt95plWroHBosn4mfzOhnKuc/gNWyaRxN9GANLBiaEAyvBGWw+upy7DX7inULVh60SA1OW5g+rzxAJbaWgsa+3c0j1ztCwrAXak2fWLR6hicHOvZ9bb7BPlgy4SWzxlYDZ/Gma+L6uLFUMTLRJe3NUkvqGkw8/UKrtSm70VKX/orplN3qO7JcUuiPe4R9Qv571VKQS5QVIAoohuSY6GgU+WnZ18I8+gV7DNDRcgwRWIxxqP08tXEpV8qVBHlYJOh5ev69CCKfLdMVTVlzfetFQWkPjYqzSmdhtLyP0MrZnXyv/L8FeQjRBPjPsppKWsiFlHDqatJn94ZViXnRCpkInUbZuA5WLXkUpQm4QK1jroGm5gNsAjRpwvlUn2gqyhHRgppT/VO/voo/bhUo/zuztEE6Ti0l0QikUikOvwFLsfM2ZFYDqIAAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFQAAAAaCAYAAAApOXvdAAADeElEQVR4Xu2YWahNYRiGPxkyZjgiUaTMJGMZyjFlCIVEKUoZMnNBEZFkKJQ5KUkSGTPHjSGJopShpORWuRBXCu/T96/2ss7e23b22edC/1tP7fWt9Y/fsP61zaKioqKioqL+b40TH8SnEpngzaLyqYE4LM6LbuEanRQ/xeRw3VCMER/FsGCLyqOO4oLokLK1Fc/NN69zyt5SnBFdUraojEjfdRnbQPFVXBSNUnY2+qBolbJFZTRH9MzY5otfYmPGXiWWWK4sRJUo6ucPMTp7I+rfVah+RtVSQ8R3q1k/61qTxGer/DjlilNOWfMsVD8rIV5w9TFOuWKeS7PGUsTL5pTVT/3kCHbLKj9OueJEc9dqOc9S6iebThpwHmXzkxNCM3MvcqadZV46ErUXW8UN81NCY9HHfKxV4prYFOyJOonN5m0WWvGTBalIv8fFKHFCLA921EvsNe9rYrChvuZr2G7+tdgu2PmImS0um7d7an5e/2f9rX6yqA3mi28hroj15tHGZNlonjkrdoY2XcVN0UNUi9fmk5sh3gc77a9azglDxQPztvS3I7QppEFimvm4PLtYPBGtzZ2Lw/hNtHGfuTP+JfOx+fJ7J7qbOxXHrDQfm3UU2o+8IsJeiC/mtTPhm3hrf0baCPHKPHoZDI8ygXnm6UuUNhXXxRTzSZyzXJ3kXpvwO10/6Y8oIGp5BgcQ6fS7Xyyy4hHKVx7reGw+X/pgo8gMHEgfvBvYKJzO5j4MvxEfN7fNN7pavLScA5knQVMRsQH5vHXaPGoRm/PI3Nuk7RurWX+y9ZOF4QQckrQZG+6VKjbynnnZStuIPLIgLewERvIJzbqSjOI3kY4Dy6qfpQhPHUld4+ne5hs6PdjYHLw9Xsw0j7z+4R7qF67Z9CTS+XOG+ktEjrRcpCWiDU4oJtrzQZIWEf/M3EmIsQaL4eYlhj5xIs6lBFB3t1guc5gn8yczmVudi5pG3VwgVog95mnPmZKX1FrzF8Idscs8bfifgJRjQvvMS8FU85Qm0oH728Rc80VT945l2hRLecS42UXTZrXYbZ7yh8wdxUbyPHM7YF7/j5q3H2CehcvC8/fNX0w4pyJK1860uKYGoSbhOlG6diLu8Uwi+kzaJqJNVbiHSDuiJ8sa89Rsbv52zic2MD1+ItrRJjs+tuQPoOxco6KiohL9Bs2LoYNjPLhqAAAAAElFTkSuQmCC>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJEAAAAaCAYAAAC3r744AAAFPklEQVR4Xu2ZeaimUxzHv7IvEzP2mJrBWLJkG7KOzFgbkqGsIdkllLXBH8iY7GNLY0sTSZasIV4R4g9RlpQ/SETxF4o/8Pvc3/l1zz33fe593pn33vdOnU99u/c951nO85zv+Z3fc45UqVQqlUqlUqlUKpWpwWamj0z/ZfrZtI9pW9NnRd23ph2HzpTOKOpeMm2Y6iqTy/qm00yPmJaadhpZ3Yq9TEeWhb1wjdwIl5YVxvXyuhPLCmMP0zumWUV5ZfLY2PSW6WbTRqY9TV+ZFuUHNbC/6WrTp/I+xgcrzelqvkiYiGNy1jAtNh1RlFcmF/oME0zPyuirr01bZmXdwETHmY41/anu/d8aLoRRMEzOLNN36m6wXeWhc+2ivDJ5YBwM9GRRPtf0h+n4orwJ0pdVNtEC078a2RgizS2mezTaRGuZbpMbqTI4djH9ptEmClPcWpQ30RcTxUXyxlC2RJ4LYaK87hDTdXKjVQZHt34bq7yJvprobfkXFlPUvaYdsrpoEMnbQ6aZ6XelHTNMb5h+6EE3DJ3ZTKQhpVnKPhuPvphoa9P3po7cJCTLl6e60mAkbRekuongQtNfah+KB8VFGnw7j9EUNBFJGtHnMdMWqS7m3Y5pe9MDcqNNFOuZXlb7pHBQ0M4X5PnkoGgyS1N5E30xUWT5GOkm08lZXRjsfdONmvhP+m3k99qurJhisBj7sdq3k/xxU/n7bKtNhs5shnuzOFyaJUxRfm030RcTEVk68i+0Z+QroEGYiLD5tJo/6Sk/RT467zRtlcp52fxeZjpKbpKAyHa36UXTCfIXzcj+0HSl6XXT2ak8YDWWpYVXNL6h+Yo83/Sw6SD5iu7FqXxN+frIE0m0EyhfZHredKbpQPnxwHthKqfuDnn72q7S837mm07qQazjjEX026vyyBjwDv9JfwPWjDBxN/piIl4EOc/f8i+vnGgoN+Fm3eAFMc2dKt9KYbuE+Zql9PfkhqKTvjEdnM7ZT24eEs5zTW/K28GDEIkox8Cd9Bf4UmR7hVXaafJV2rE6kfsvNK2QH3ue3KC0kfZeJTfo3FSHWShn5Z5yRvJzqZx70llHp9+UDzIfCth+IgmfnX7Tbp6VKEmbgYH3i+nH7LicXiNXI4TE5RoedUGYiIblESGHCPSu/FhGMo5fVx65YiuF3Ip9OkYED0dnRt7DeajMh3i4D+Sdjr403SVP7okudOhYkNex18c1uBbX5z6M0F/lSTwJMs+NyQ8wfaLhld775BERMPpr8mgU7WSgDBoGMF/LvH+iOf3Ee2L7I+DZPpcHijAW8Pw/aeQe6O/yQRw5cU/wkumobuwtjwxNYMByVBI9vpCPcsAYz8pNyr3Y3ynziTIfwoD3y83LOUSyOamuLZzH3lK+LUC0Y9otp2bKiVrcD7NhmoicPGOM1F7zoYmG9jJYmAIP1ejnWi1gJF+S/Wb6wjwduZl4SMzAqD7HdLg8Em2ejqceo86TdxwdyIhntJP3XCbPTYgSMbXFOWXkLCGHoX1lGaYIGJ07y00UecFucqMQnYi0HM+6DBAByYfIcQ5LZZVVZF/5yOZl0wnXajhnWWy6XZ6wP266wrSOfDuFkc3URNJNxMBkEdEwEtMhu8x0FqbBTEuKc8aDZJp25WCaR+XhHPPTPiLt7vJch3KmS8I/STxTMR8FT8nb8KB84ZCtn5UK+5XuRC7E35xYAY//87wqcqEAc+WhmGttkP0Gjs8/fUm2WdktdZb8epxftgloB+0lv8nhWAYA0BauEfA7EvmyrZVKpVKpVFZP/gfNpBRC0OSHegAAAABJRU5ErkJggg==>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADsAAAAaCAYAAAAJ1SQgAAAC+klEQVR4Xu2XSahOYRjH/zKEDBlCUS5FKRYylKksEBkSmZIoGRZWNoaoa2FhLCRCSZIxNmQslyzs2NhRFmQhKWFBhv/vPud1vvNd3aGuj0/fv359p/d5zznvM73n/aSaaqqpppr+PU02b8yPjGemf2FGUTPNN8Vcfu+ZfoUZVaD95rV5ZYaU2ZJw6rz5YK6YTkVzdaiHOWsOmU9mXNHcqA5mo9lmvpvNRXP1aLg5aZYqynN+0dyosQpnt5qvZmrRXD1aoMjYBPNZTbPWzdSbweaGeWEGlk6oJtWbGWaUeWd2F6zSMoUdZ1/qP+hXNiWyRdbOKXoU1ZktCudw+L/o164KxxsyuMZBHK2LqY3XlejX2eatmq+gnsq/DLRfq5T6FZFNspp6kkxSwohgVLJfD5sN5YNlou3uq/lzQUH1CqeS6Ff6drrZo9icEGXON7i5aLeXyNpttVxBK9WG9VCqlAKlnEQ/siPzED43Sb/rV16y3hw3I8x2c9PMMpPMRXPUDEo3WJ3NcnMts9Vl4x3NYnPV7DWPlVcQAece1nTA9M7GW5P9X5pirisimcQ3lm8tpZ02KUTGy/uVYMxTlP4xxaI4kHD8XJTN2ac8QDiKgysUz6bXLpleioBtysZ5V8oYjhEYAoEWmjmmj3mglrOvaea98vPwF7M2s7HYO8rPuwfNx2xemnvL9DUDzEjzSPmpiz0AB1gocM0YIjv0GBWFuOepwpEnyjNJxlKAyNxzs0qxQabMtrlf20Ms+K4i0oissCg0TBEIftGZzJ5EzzWYnco/d+X9yj3sHaVVhtrUr+0lXnpasRgyRlWkDQ8be8JEM9ecMmsyGyV/WZFVgpMCNFrRr/Q8lUCWkw3R/0OzcbK+WhXM7gnFohCLeKg4aSHGL5hditIbr2gBFkiAliiCNEaRJc7eRxR/G9mkKFWeyTMIHE5zNidQO7K569Q0639M3RU7KeKlXUpsiLJMdsQ1+0HpWBpPGyUbWelzsJE9xpNSyVfM0Zpq+kv6CdWGkMJ/N/oaAAAAAElFTkSuQmCC>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA0CAYAAAA312SWAAAD5ElEQVR4Xu3dXahmUxgH8CVMvmZkTCRikhRGk2ZcEDe4QJGQG8WNMKmpUTIpNSUXmisSko9BhJSECOWruFCSyIXkIx/lghI3xHieWWt3ln3ec2bOOe/UW36/+vfu/ey93z3zXj2ttfY+pQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAsM9Oj3wYeS5ya+SNyBmRi/qTpuDYyO4F8lbk0sh3i2Sp/561Ze77J137WanHfoicPzoGADAzDo78Gdne1bJ5+S1yQleblstKbZJ6R0eejtwfWR85IPJI5J92/MDIN5Gz2/5SZKP2deTKUT3v8VXkp1EdAGCm3Fxq85TNy9gT48KU5Eha3ySta58PRbZ19WwYX+j274us7vb31YORC8t//z9HRHZE/ojc3dUBAGbOj5Evx8UmR7j2h2zW3mnb2ShubNu3RU5t2ykbydu7/RvL5MZyb54sdaQwG8XDW+26yHml3uOSVgMAmDk5ypRTjpPWdi3mzjJ/bVmf1+dOnSibpJ8j30f+Hh0bHFXqFOjxo/pyDFOheb9s3HIKOD9zZK9v4gAAZs5xpY52nTw+sB9lk9jf847uWK5TG2wqdTr0oK42yebI1nGxk9ef1rZz+jO/dxhRy+2VTodmQ/lemf8b5n13lvnr5gAAliRHsb4ttXEbeyxyzLjYZNOV1yyUha5Ll5fJTVJOhw5y2vPxUqcs9+bQyJpxsdN/x1+lrtnLp1/zHvmQw7jRWo6+6ezlvfM3BgBYkZwSvXhUy2bmqlGtd2bk6kWy2JqwbNbGx08p9TUig2xyPirTmQ7t18DlQwxvtu2cDv28zE2H5pOrz0duiLxW6lq6XMM3rKnL3yR/p6ciZ7Vavgrl3sgHbT9HCHe1pJvaJwDAiqwvteHYFbk+8n7kgu74tOSoW373sH4t17r90vZ/jWwotTn6uNUyv0e+yIuXIV8TMnzPs5HDIq+W+rqSXLM3HMvXfZwbOTHy8p4r61TpMDI2NHyfltpA5gjiJ6U2lNnA5Xdlg5ef+f/aUmqjlw3h23uuBACYghw9uqKlX0f2f5LNWDaU6dpSf5MjI+e02rCeLqc5c2QuG7h8cCGnQ3PUMBu7F9u5Kc97t9sHAGCF8q877Ci1SRuecs1m7a7ISZFXSn2tSJ6XT5k+XOo7416KPFDqdY9GboncE7km8kw7FwCAKVhV5pqrQ7r6UMsRt/wzV718iW/Wh3Vwud1fu5yX/AIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALPpX2SglwwMHYEZAAAAAElFTkSuQmCC>