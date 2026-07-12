---
id: DDD-DSC-001
title: "bitz-ddd プロダクトビジョン（Vision Board + PR-FAQ 圧力試験）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# ビジョン（Vision Board + PR-FAQ）

> 遡及 discovery。bitz-ddd はリリース済み（plugin v0.1.1 / 各スキル v0.1.0、created 2026-07-10）。
> ここでは「なぜこのプラグインが存在するか」を後付けで明文化し、以後の DDD- 起票の錨とする。

## Product Vision Board（Roman Pichler）— 5要素

1. **Vision** — BitzSDD の仕様駆動フローに、必要なときだけ「本格 DDD の設計規律」を差し込めるようにし、
   個人〜小規模の開発者が重厚な DDD 教科書を通読せずとも、ドメインを言葉から正しくモデル化できる世界。
2. **Target Group**（セグメント必須）
   - **主要**: BitzSDD を使う個人開発者（現時点では作者 hide 本人。ドッグフーディング）。
   - **二次**: 将来の OSS 利用者のうち、bitz-sdd を導入済みで DDD の設計手法を求める開発者。
   - **除外**: bitz-sdd を使わない開発者（併用前提のため単体では機能しない）／大企業のドメインエキスパート集団による
     イベントストーミング・ワークショップ運用（本プラグインは AI エージェント主導の軽量導出が前提）。
3. **Needs**（解決する問題）
   - sdd-design の軽量デフォルト設計だけでは、複雑ドメインで「概念の取りこぼし」「集約境界の恣意性」が起きる。
   - DDD を正しく回すには戦略設計〜戦術設計〜ブラウンフィールド評価の作法が要るが、
     個人開発者が毎回それを思い出し・適用するのはコストが高い。
   - 上流のドメインストーリーから要件（EARS 節）への根拠あるトレースが欲しい。
4. **Product**（際立つ少数の差別化要素、機能全リストではない）
   - **ddd-story**: Domain Storytelling でペルソナ×重要ジョブのハッピーパスを物語化し `.spec/design/stories/` に残す。
   - **ddd-model**: 戦略設計＋戦術設計（Entity/VO/Aggregate、境界づけられたコンテキスト）を**2パス導出必須**で
     `.spec/design/domain-model.md`（DSN- 体系）に落とす。
   - **ddd-evaluate**: 既存コードの DDD 12基準＋MMI 4軸をブラウンフィールド評価し統合改善計画に繋ぐ。
   - 共通の差別化: **bitz-sdd との契約（artifact-frontmatter 公開契約）に完全準拠**し、成果物が SDD ライフサイクルに
     そのまま流れる。DDD 手法を「独立ツール」ではなく「SDD の設計工程の差し替え可能なプロバイダ」として提供する。
5. **Business Goals**
   - 直接の収益目標なし（OSS / 個人開発）。ゴールは **BitzSkills エコシステムの設計品質の底上げと再利用性**、
     および作者自身の開発（ドッグフーディング）での設計欠陥の早期発見。
   - 将来的な間接便益: bitzskills マーケットプレイスの魅力向上・OSS 採用者の獲得。数値目標は `TBD`。

**Mission**: bitz-sdd の設計工程に、ドメインストーリー → ドメインモデル → 成熟度評価という DDD の規律を、
AI エージェントが自己完結スキルとして必要時に注入する。
**Values**: (1) SDD 契約への準拠を最優先（独立を主張しない）。(2) 根拠のないモデル要素を捏造しない
（2パス導出・根拠記録の強制）。(3) 手法は自己完結、連携はスキル名の言及で行う。

## PR-FAQ（圧力試験）

**プレスリリース（要約）**
見出し: 「BitzDDD — BitzSDD に本格 DDD の設計規律を差し込むプロバイダ」。
BitzSDD を使う開発者は、複雑ドメインに直面したとき sdd-design の軽量設計から ddd-story / ddd-model /
ddd-evaluate へ切り替え、ドメインを言葉からモデル化し、成果物を SDD ライフサイクルにそのまま流せる。
差別化は「独立 DDD ツールではなく、SDD の設計工程を置き換える契約準拠プロバイダ」である点。

**外部 FAQ（抜粋）**
- 価格: 無償（OSS、bitzskills マーケットプレイス経由）。
- 使い方: `agy plugin install` / `/plugin install bitz-ddd@bitzskills`。**bitz-sdd の導入が前提**。
- 単体で使えるか: いいえ。`.spec/design/` 契約と sdd-core の artifact-frontmatter に依存する。

**内部 FAQ（荷重を受ける部材）**
- 市場規模: TAM/SAM/SOM とも `TBD`（OSS のため厳密な市場定義は未実施。実利用者は現状1名＝作者）。
- 競合状況: 詳細は positioning.md（DDD-DSC-005）。
- リスク: (1) bitz-sdd への強結合＝bitz-sdd の契約変更に追従コスト。(2) 外部 OSS 利用者の需要が未検証。
  (3) AI 主導の DDD 導出の品質が「本物の DDD ワークショップ」に劣る可能性。
- **Go/No-Go 基準**（後段 assumptions.md が執行）:
  - D1: 個人開発者が sdd-design 単体では足りず DDD 手法を実際に呼び出す場面が存在する
    → **作者のドッグフーディングで最低1回、ddd-story→ddd-model の一連が実運用で使われたら Go 寄り**。
  - F1: 3スキルが bitz-sdd 契約下で成果物を破綻なく生成できる → 既にリリース済みで検証可能。

## Open Questions

- 外部 OSS 利用者の実需要（Desirability）は未検証。`TBD`。
- SI-CORE-014 による 3段階読み込み化・スクリプト化後も本ビジョンが不変か（構造変更のみのため不変の見込み）。
