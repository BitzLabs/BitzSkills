### SDD（仕様駆動開発）品質管理およびバリデーション詳細仕様書

#### 1\. 品質管理の根本思想：バリデーション中心設計（Validation-Centric Design）

AI駆動ソフトウェア開発において、品質管理のパラダイムは「人間による事後レビュー」から「AI/CIによる仕様基準のバリデーション」へと転換されなければなりません。従来の開発では、仕様書は実装の「参考資料」に過ぎず、時間の経過とともにコードと乖離する「Spec Drift（仕様の腐敗）」が常態化していました。SDDでは、機械可読な仕様書（Living Spec）を「唯一の正（Single Source of Truth）」と定義し、実装が仕様に100%忠実であることを機械的に保証します。このバリデーション中心設計は、AIエージェントの自律性を制御し、大規模システムの品質を数学的・セマンティックに担保するための戦略的基盤となります。

##### 職務分掌（Separation of Duties）の定義

SDDのアーキテクチャでは、創作を担う\*\*ImplAgent（実装エージェント） **と、評価を担う** AuditAgent（監査エージェント）\*\*の物理的・論理的分離を必須とします。 人間による開発と同様、実装者自身がテストやレビューを行う場合、「自己承認バイアス（Self-Approval Bias）」が不可避であり、自身のハルシネーションや設計の論理破綻を見落とすリスクが極めて高くなります。ImplAgentに「仕様の具体化とコード生成」の責任を、AuditAgentに「仕様との整合性監査」の責任を独立して持たせることで、システム的な牽制機能を働かせ、ハルシネーションを構造的に排除します。

##### 基本原則

* **Absolute Grounding（絶対的帰属）** : すべてのコード、テスト、設計決定は、必ず上位の仕様書（REQ/TECH）に明示された根拠に帰属しなければならない。  
* **Verification vs. Validation（検証と妥当性確認）** :  
* **Verification（検証）** : 詳細仕様（TECH）の構造とコードの一致を物理的に確認する（Gate 2, 4-A担当）。  
* **Validation（妥当性確認）** : 実装成果物が要求仕様（REQ）のビジネス目的・受入基準に適合しているかを意味的に確認する（Gate 1, 4-B担当）。  
* **Zero Spec Drift（仕様乖離ゼロ保証）** : 実装中に判明したエッジケースは即座に仕様書へ逆同期され、コードと仕様の乖離を常にゼロに保つ。次のセクションでは、これらの思想を物理的に強制する5つの品質ゲートについて詳述します。

#### 2\. 5つの品質管理ゲート（Gate 1-5）の詳細定義

開発ライフサイクルの各フェーズに配置されたゲートは、品質低下を未然に防ぐ防波堤として機能します。各ゲートは「仕様の品質」と「実装の忠実度」を厳密に検査し、不適合がある場合は後続フェーズへの遷移を物理的にブロックします。

##### Gate 1: 要求仕様検証ゲート (Requirements Validator)

要求仕様（REQ）が、AIが実装可能かつテスト可能な精度に達しているかを審査します。

* **入力** : 01\_requirements.md (Draft)  
* **検証項目 (EARS-AI v2 構文チェックリスト)** :  
* ACTOR, CAPABILITY, BUSINESS\_RULE タグによる要件の構造化。  
* GENERATE, CONSTRAINT, IF\_ERROR によるAIへの指示と制約の明示。  
* 曖昧さの排除（「〜しやすい」「適切に」等の検知）。  
* デッドエンド（矛盾するビジネスルール）の検知。  
* **出力** : 承認済み 01\_requirements.md (Approved)

##### Gate 2: 設計整合検証ゲート (Design Compliance Validator)

要求仕様（REQ）と詳細仕様（TECH）のトレーサビリティを「検証（Verification）」します。

* **入力** : 01\_requirements.md (Approved), 02\_technical\_spec.md (Draft)  
* **検証項目** :  
* YAML Frontmatterの relations.parent によるリンク整合性。  
* 循環参照の検知。  
* **ステータス不整合チェック** : 親（REQ）がDraftのまま子（TECH）をApprovedにすることを禁止。  
* **出力** : 承認済み 02\_technical\_spec.md (Approved)

##### Gate 3: 自律実装・単体テスト検証ゲート (Self-Healing Implementation Guard)

実装が技術規約およびテスト基準を完全に満たしているかを検証します。

* **入力** : 02\_technical\_spec.md (Approved), プロジェクト憲章（Constitution）  
* **検証項目** :  
* **TDDの強制** : テストコードが先行生成され、期待される挙動が定義されているか。  
* **ビルド・静的解析** : リンター、型検査、セキュリティスキャンのパス。  
* **100%通過** : すべてのテスト実行結果がSuccessであること。  
* **出力** : 実装済みコード, テストレポート

##### Gate 4: 仕様・実装セマンティック突合ゲート (Two-Tier Compliance Auditor)

成果物が事前の契約（仕様）と完全に一致しているかをAuditAgentが二段階で監査します。

* **入力** : 実装コード, テストレポート, REQ/TECH  
* **検証項目** :  
* **Phase A: 構造突合（Verification）** : 実装されたAPIシグネチャ、型定義がTECHのデータ契約と一致しているか。過剰設計（仕様外の実装）の検知。  
* **Phase B: 振る舞い突合（Validation）** : パスしたテスト内容がREQの受入基準（AC）およびEARSタグの条件を網羅しているかのセマンティック監査。  
* **出力** : Compliance Passed 通知

##### Gate 5: Living Spec同期・監査ゲート (Living Spec Auditor)

実装過程で得られた知見を仕様書へ反映し、Spec Driftを解消します。

* **入力** : 最終実装コード, REQ/TECH  
* **検証項目** :  
* **リバース同期** : 実装中に決定した詳細ロジック（IF\_ERROR等）の仕様書への逆反映。  
* **最終化** : フロントマターの status を verified へ、updated\_at を現在時刻へ更新。  
* **出力** : 最新のLiving Spec, マージ可能PR

#### 3\. トレーサビリティ自動検証エンジンのアーキテクチャ

静的なグラフ解析（構造的整合性）と動的なAI監査（セマンティック妥当性）を組み合わせたハイブリッド検証アプローチを採用します。

##### 3.1 静的グラフ検証エンジン (Python & NetworkX)

仕様書間の親子関係、依存関係、およびステータスの整合性をDAG（有向非巡回グラフ）として構成し、不整合を検知します。  
import networkx as nx  
import frontmatter  
from pathlib import Path  
import sys

def validate\_spec\_graph(specs\_dir: str):  
    G \= nx.DiGraph()  
    specs\_path \= Path(specs\_dir)  
    errors \= \[\]  
      
    \# 1\. グラフの構築とフロントマターのロード  
    for md\_file in specs\_path.rglob("\*.md"):  
        post \= frontmatter.load(md\_file)  
        spec\_id \= post.get("id")  
        if not spec\_id: continue  
          
        G.add\_node(spec\_id, path=md\_file, \*\*post.metadata)  
          
        relations \= post.get("relations", {})  
        if relations.get("parent"):  
            G.add\_edge(relations\["parent"\], spec\_id, type="parent\_child")  
        for dep in relations.get("dependencies", \[\]):  
            G.add\_edge(dep, spec\_id, type="dependency")

    \# 2\. 検証ロジック  
    \# 循環参照チェック  
    try:  
        cycle \= nx.find\_cycle(G, orientation="original")  
        errors.append(f"Cycle detected: {cycle}")  
    except nx.NetworkXNoCycle: pass

    \# ステータス整合性チェック: 親がDraftなのに子がApprovedなのはNG  
    for parent, child in G.edges(data=True):  
        p\_data \= G.nodes\[parent\]  
        c\_data \= G.nodes\[child\]  
        if p\_data.get('status') \== 'draft' and c\_data.get('status') \== 'approved':  
            errors.append(f"Status Inconsistency: Child '{child}' (approved) cannot have Parent '{parent}' (draft).")

    return errors

##### 3.2 動的セマンティック突合 (AI Audit Agent)

AuditAgentは、EARS-AIタグ（WHEN, THEN等）と受入基準（AC-x）をテストコード（Assert）に自動マッピングし、カバレッジを判定します。

###### *Gate 4 検証フロー図*

sequenceDiagram  
    participant I as ImplAgent (Code/Tests)  
    participant S as Specs (REQ/TECH)  
    participant A as AuditAgent  
    participant G as Quality Gate 4

    A-\>\>S: 構造定義(ENTITY/INTERFACE)とACを抽出  
    A-\>\>I: 実装コードとテスト実行ログを取得  
    Note over A: Phase A: Structural Matching  
    A-\>\>A: TECH定義 vs 実装シグネチャを比較  
    Note over A: Phase B: Behavioral Validation  
    A-\>\>A: REQ受入基準 vs テストSuccess項目を突合  
    A-\>\>G: 監査レポート(Compliance Report)を発行  
    G--\>\>I: 適合(Pass) or 乖離(Fail)を通知

###### *JSON Schema: フロントマター・バリデーション*

フロントマターの機械可読性を保証するため、以下のスキーマを適用します。  
{  
  "type": "object",  
  "required": \["id", "status", "relations"\],  
  "properties": {  
    "id": { "type": "string", "pattern": "^(REQ|TECH|MS)-\[0-9\]{3}$" },  
    "status": { "enum": \["draft", "review", "approved", "implementing", "verified", "spike"\] },  
    "relations": {  
      "type": "object",  
      "properties": {  
        "parent": { "type": \["string", "null"\] },  
        "dependencies": { "type": "array", "items": { "type": "string" } },  
        "implements": { "type": "array", "items": { "type": "string" } }  
      }  
    }  
  }  
}

#### 4\. リトライループとエラーハンドリングの制御

自律型エージェントの「手戻り」を最適化し、暴走を防ぐためのフィードバックループ制御を定義します。

##### フィードバックループの動作

1. **エラー診断** : AuditAgentが失敗理由（契約違反、ロジック不備等）を特定。  
2. **自己修復（Self-Healing）** : 修復可能なエラーに対し、ImplAgentへ修正指示を発行。  
3. **リバースエンジニアリング** : 実装中の妥当な変更を検知した場合、Gate 5を通じて仕様書を更新。

##### 閾値と人間介入 (HITL)

1. **リトライ制限** : 同一タスクに対する自己修復は最大3回まで。  
2. **HITLトリガー** : リトライ上限到達時、またはREQレベルのビジネスルール競合を検知した際。  
3. **Spikeフォールバック** : 難解な技術課題や未知のエラーによりGate 3/4を通過できない場合、以下のフローを実行する。  
4. 対象仕様の status を spike に変更。  
5. 既存の実装を一旦隔離し、プロトタイプ検証モードへ移行。  
6. 「Reverse Engineeringスキル」を起動し、プロトタイプの結果を事後的に仕様化して正規ゲートへ再合流させる。

#### 5\. 結論と戦略的サマリー

本仕様書が定義する「バリデーション中心設計」と「5段階の品質ゲート」は、AI駆動開発における信頼性の源泉となります。ImplAgentとAuditAgentを分離し、機械的なトレーサビリティ検証を徹底することで、人間のレビュー負荷を最小化しつつ、極めて高い「Fidelity（忠実度）」を維持した開発が可能になります。この体系によって実現される「Living Spec」は、いかなるSpec Driftも許さず、ビジネス要求とコードが常に1対1で対応することを保証します。これは、エンタープライズ級のAI自動開発において、速度と信頼性を両立させるための唯一の技術的回答です。  
