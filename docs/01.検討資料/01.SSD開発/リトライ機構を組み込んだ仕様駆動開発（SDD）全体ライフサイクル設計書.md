### 仕様駆動開発（SDD）におけるリトライ機構統合型ライフサイクル・デザインレポート

#### 1\. SDDライフサイクルの基本設計：二層構造と5フェーズの再定義

仕様駆動開発（Specification-Driven Development: SDD）の本質は、仕様書を「唯一の正（Single Source of Truth: SSOT）」として再定義し、開発プロセスの全域でAIエージェントの行動を統制する「動的な契約」として機能させることにあります。従来、仕様書は実装の進展に伴い形骸化する運命にありましたが、SDDでは機械可読な仕様書をインターフェースとすることで、AIのハルシネーション（もっともらしい嘘）を構造的に排除し、開発の信頼性を決定論的なレベルまで引き上げます。

##### 1.1 要求仕様（Requirements）と詳細仕様（Technical Spec）の分離

AIエージェントのコンテキスト効率を最適化し、人間による意思決定と技術的実装を分離するため、仕様書を以下の二層で管理します。| 項目 | 要求仕様（Requirements Spec） | 詳細仕様（Technical Spec） || \------ | \------ | \------ || **問い** | **Why & What** （背景・目的・ビジネス価値） | **How & Contracts** （実装手段・内部契約） || **主要な読者** | 人間（PO/Stakeholder）＋ 仕様生成AI | AI実装エージェント ＋ 技術監査担当 || **主要記述内容** | ACTOR, CAPABILITY, BUSINESS\_RULE, 受入基準（AC） | ENTITY, INTERFACE, STATE, IF\_ERROR, データスキーマ || **検証視点** | **Phase B: Behavioral** （振る舞いとACの網羅性） | **Phase A: Structural** （型・インターフェースの整合性） |

##### 1.2 フロントマターによるメタデータとDAG管理

各仕様ファイルには、Pydantic等のスキーマ検証に対応したYAMLフロントマターを実装します。これにより、仕様間の依存関係を有向非巡回グラフ（DAG）として動的に管理し、AIが必要なコンテキストを自動収集可能にします。  
\---  
id: TECH-001  
title: 配管・配線インピーダンス計算 詳細設計  
type: technical\_spec  
status: implementing  
version: 1.1.0  
milestone: MS-001  
relations:  
  parent: REQ-001  
  children: \[\]  
  dependencies:  
    \- TECH-000-COMMON-TYPES  
  implements:  
    \- src/Calculators/ImpedanceCalculator.cs  
  tests:  
    \- tests/Calculators.Tests/ImpedanceCalculatorTests.cs  
\---

##### 1.3 標準5フェーズの解説

1. **Intent & Spec Generation:**  人間の意図をEARS-AI記法で構造化。Gate 1で要件の妥当性を承認。  
2. **Architecture & Execution Planning:**  境界づけられたコンテキストに基づきタスクグラフを作成。Gate 2で設計を承認。  
3. **Autonomous Implementation & TDD:**  AIがテスト先行（Red-Green-Refactor）で自律実装。  
4. **Spec-Grounded Verification:**  二段階（Phase A/B）で仕様と実装の突合検証を実施。  
5. **Living Spec Synchronization:**  実装時に得られた知見（エッジケース等）を仕様書へリバース同期。**「So What?」レイヤー:**  単なる対話型プログラミング（Vibe Coding）は、会話ログの肥大化による「文脈の風化（Context Rot）」を招きます。本アーキテクチャは、仕様を物理的なドキュメントとして固定し、AIの推論を常に「静的な構造」と「動的なルール」の制約下に置くことで、長期プロジェクトにおける保守性とAIの予測可能性を極大化します。

#### 2\. 多重リトライループ（Retry Loops）の体系的統合

AIエージェントによる開発では、エラーは回避すべき事象ではなく、解決すべき「シグナル」です。本レポートでは、エラー発生を前提とした「自己修復型ワークフロー」を各階層に統合し、開発スループットを最大化する設計を提案します。

##### 2.1 実装レベル：Self-Healing Loop

AIエージェントがTDDサイクルを回す際、ビルドエラーやテスト失敗を検知した瞬間に発動するループです。

* **修復サイクル:**  エラーログを解析し、コードを修正。修正案が失敗した場合は、過去のDiffを参照し、同一の誤りを回避します。  
* **プロジェクトメモリへの記録:**  各リトライの結果は /gsd-commit-memory コマンドを通じて .antigravity/memory/ に永続化されます。これにより、セッションを跨いでも「一度失敗したアプローチ」を繰り返さないガードレールを形成します。  
* **介入（HITL）条件:**  
* リトライ回数が上限（5回）を超過。  
* プロジェクトメモリにより「論理的デッドエンド（仕様の矛盾）」が指摘された場合。

##### 2.2 検証レベル：Spec-Grounded Feedback (Gate 4\)

Gate 4での突合検証において、仕様から逸脱（Spec Drift）したと判定された際のリトライです。監査エージェントが生成した「乖離レポート」をプロンプトとして実装エージェントへ差し戻し、自律的な修正を促します。

##### 2.3 策定レベル：Validation Dead-end Retry (Gate 1/2)

仕様策定時、Validatorが「テスト不可能」または「論理的矛盾」を検知した際に発動します。仕様生成エージェントに対し、上位要件（REQ）との整合性を再確認させ、仕様書の品質自体をセルフヒーリングします。**「So What?」レイヤー:**  自動リトライの統合により、人間は「デバッガー」という認知負荷の高い役割から解放され、「検証済み成果物の最終承認者（Reviewer of Validated Outcomes）」へとシフトします。人間が介入すべきポイントは「戦略的方針の転換」や「リトライ上限到達時」に限定され、開発全体のリードタイムが劇的に短縮されます。

#### 3\. EARS-AIによる動的な状態遷移ロジックの定義

リトライを含む複雑なワークフローをAIに誤解なく実行させるため、拡張EARS記法（EARS-AI）を用いて状態遷移を形式化します。自然言語に近いこの記法は、AIの注意機構（Attention）に対する強力な意味的制約として機能し、ハルシネーションを抑制します。

##### 3.1 リトライプロセスの状態遷移定義

\#\#\# リトライ制御および生成ロジック  
\- \*\*\[STATE: Running\]\*\* タスク実装中  
    \- \*\*\[ENTITY: CodeContext\]\*\* 実装中のソースコードおよびテスト  
    \- \*\*\[WHEN\]\*\* \`\[EVENT: TestFailed\]\` が発生した場合  
    \- \*\*\[THEN\]\*\* \*\*\[NEXT\_STATE: Healing\]\*\* へ遷移する

\- \*\*\[STATE: Healing\]\*\* 自己修復中  
    \- \*\*\[BUSINESS\_RULE\]\*\* \`.antigravity/memory/\` 内の過去の失敗履歴を参照し、同一の修正を繰り返さないこと  
    \- \*\*\[GENERATE\]\*\* 修正された \`{CodeContext}\` を生成し、テストを再実行する  
    \- \*\*\[IF\_ERROR\]\*\* \`RetryCount \>= MaxLimit\` の場合  
    \- \*\*\[THEN\]\*\* \*\*\[NEXT\_STATE: Failed\]\*\* または \*\*\[NEXT\_STATE: Spike\]\*\* へ遷移する

##### 3.2 全体ステートマシンの視覚化

stateDiagram-v2  
    \[\*\] \--\> Gate1\_REQ: Intent  
    Gate1\_REQ \--\> Gate2\_TECH: Approved  
    Gate2\_TECH \--\> Phase3\_Impl: Approved  
      
    state Phase3\_Impl {  
        \[\*\] \--\> CodeGen  
        CodeGen \--\> Testing  
        Testing \--\> CodeGen: \[EVENT: Failure\] / Self-Healing  
        Testing \--\> \[\*\]: \[EVENT: Success\]  
    }  
      
    Phase3\_Impl \--\> Gate4\_Verify  
    Gate4\_Verify \--\> Phase3\_Impl: \[EVENT: SpecDrift\] / Retry  
    Gate4\_Verify \--\> Gate5\_Sync: Approved  
      
    Gate4\_Verify \--\> Phase\_Spike: \[EVENT: RetryExceeded\]  
    Phase\_Spike \--\> Gate5\_Sync: Reverse Spec Engineering  
      
    Gate5\_Sync \--\> \[\*\]: Verified

**「So What?」レイヤー:**  状態遷移のタグ化（STATE, EVENT等）により、AIは「自己の現在のフェーズ」と「適用されるべき具体的制約」を客観的に認識します。これは、実装中にAIが勝手に仕様を書き換えてしまうような、SDDの原則に反する振る舞いを構造的に防止する「実行可能な憲法」として機能します。

#### 4\. 品質管理プラグイン（Gate 1-5）とリトライトリガーの連携

各ゲートの品質管理をコアライフサイクルから切り離し、Pythonベースの「スキルプラグイン」としてモジュール化することで、SDD基盤に高度な拡張性と厳密な検証ロジックをもたらします。

##### 4.1 主要プラグインの役割

* **Spec Validator (Gate 1/2):**  EARS-AI構文のチェックおよびテスト可能性の検証。  
* **Two-Tier Compliance Checker (Gate 4):**  
* **Phase A (Structural):**  ENTITYやINTERFACEと実装コードの型・シグネチャの完全一致を検証。  
* **Phase B (Behavioral):**  実装されたテストがACを100%網羅しているかを検証。  
* **Self-Healing Synchronizer (Gate 5):**  実装過程で判明したエッジケースを仕様書へリバース同期。

##### 4.2 Pythonによる自動検証・DAG管理の実装例

from pydantic import BaseModel, Field  
import networkx as nx  
import typer

class SpecFrontmatter(BaseModel):  
    id: str \= Field(..., pattern=r"^(REQ|TECH)-\[0-9\]{3,}$")  
    status: str  
    relations: dict \= Field(default\_factory=lambda: {"parent": None, "dependencies": \[\]})

def validate\_spec\_dag(specs\_dir: str):  
    """NetworkXを使用して仕様間の依存関係(DAG)を検証する"""  
    graph \= nx.DiGraph()  
    \# 仕様ファイルをロードしグラフを構築  
    \# 循環参照の検知  
    try:  
        cycle \= nx.find\_cycle(graph, orientation="original")  
        raise Exception(f"Cycle detected: {cycle}")  
    except nx.NetworkXNoCycle:  
        print("✅ DAG validation passed.")

@app.command()  
def verify\_compliance(tech\_id: str):  
    """Phase A & B の二段階突合検証を実行 (Gate 4)"""  
    \# 監査AIが仕様とDiffを突合。不合格時は非ゼロの終了コードを返しリトライを誘発  
    result \= audit\_engine.check(tech\_id)  
    if not result.is\_compliant:  
        typer.secho(f"❌ Spec Drift detected in Phase {result.failed\_phase}", fg="red")  
        raise typer.Exit(code=1)

**「So What?」レイヤー:**  スキルプラグインによる自動化は、品質チェックの厳格さと開発速度のトレードオフを解消します。人間が行えば数時間を要する「コードと仕様の完全一致確認」をAIが数秒で完了させ、不備があれば即座にリトライをトリガーすることで、プロジェクト全体の品質の底上げを強制します。

#### 5\. 高度な救済策：Spikeフォールバックとリバースエンジニアリング

自動リトライで解決できない難解な課題や、未知の技術スタックに直面した場合の最終手段として「Spikeルート」を定義します。これは「仕様から作る」SDDの原則を一時的にバイパスし、不確実性に対応するための戦略的ルートです。

##### 5.1 Spikeフォールバックの実行フロー

1. **リトライ上限到達:**  自律実装での解決が不可能と判断された場合に宣言。  
2. **Spike実行:**  仕様を一時無視し、AIと人間の対話を通じて「動くプロトタイプ」を試行錯誤（Vibe-ish）しながら作成。  
3. **Reverse Spec Engineering:**  成功したプロトタイプから、AIが逆にTECH仕様およびREQ仕様を抽出・生成。  
4. **正規ルート合流:**  生成された仕様を人間が承認し、Gate 5へ同期。

##### 5.2 Living Specの整合性維持

Spikeで得られた知見は、必ず /gsd-commit-memory を経由して仕様書へ書き戻されます。これにより、「とりあえず動くコード」が負債化するのを防ぎ、プロジェクト全体の知識ベース（Living Spec）の整合性を維持します。**「So What?」レイヤー:**  Spikeルートは、SDDを「重厚長大で硬直的なウォーターフォール」に変えてしまうリスクを回避します。実験的な実装（Agility）を許容しつつ、その成果を厳密に仕様書へ「再キャプチャ（Reliability）」することで、AI時代の高速開発における柔軟性と堅牢性を両立させます。

#### 6\. 結論：自律的自己修復サイクルがもたらす開発の未来

本レポートで提案した「リトライ機構統合型SDDライフサイクル」は、AIエージェントの自律性を最大限に引き出しつつ、決定論的な品質を保証する次世代のソフトウェア開発アーキテクチャです。

1. **戦略的利点:**  仕様をSSOTとし、多重のリトライループと品質ゲート（Phase A/B）を設けることで、人間が介在せずとも「仕様に準拠した動作」が常時保証されます。  
2. **今後の展望:**  AIモデルの進化に伴い、リトライ機構は単純なエラー修復から、より高度な「推論ベースの自己最適化」へとシフトしていきます。仕様を「唯一の正」とし、その整合性をAIが自己修復的に守り続けるこの体制こそが、複雑化するAI時代の開発における最も堅牢な基盤となります。

