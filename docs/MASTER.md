---
id: DOC-master
title: "BitzSkills — 文書索引"
status: active
version: 1.1.0
changeImpact: medium
project_type: library
updated: "2026-07-27"
owner: hide
superseded_by: null
optional_chapters:
excluded_paths: "調査報告, 翻訳規約"
---

# BitzSkills

> 一文サマリ: BitzLabs でAIエージェントを用いて開発する際の標準作業環境を、Agent Skills
> オープン標準に準拠したクロスプラットフォームなプラグイン群として定義・検証・配布するモノレポ。

- **種別**: `library`（プラグイン／スキルを配布する。実行アプリではない）
- **主要技術**: Markdown（SKILL.md）+ Python 3（検証・運用スクリプト）
- **配布形態**: マーケットプレイス `bitzskills` 経由のプラグイン配布（Claude Code / Antigravity 2.0 / OpenAI Codex CLI）
- **正 (source of truth)**: 意図＝このツリー / 契約・状態＝`.spec/`

## 文書レジストリ

| id | 文書 | area | status | version | 概要 |
|---|---|---|---|---|---|
| DOC-context-mission | [ミッション・ビジョン](00_はじめに/ミッション・ビジョン.md) | context | active | 1.0.0 | 目的・ゴール・Vision Board・PR-FAQ |
| DOC-context-non-goals | [対象外](00_はじめに/対象外.md) | context | active | 1.0.0 | 標準環境の定義とスコープ境界（MoSCoW） |
| DOC-context-glossary | [用語集](00_はじめに/用語集.md) | context | active | 0.1.0 | BitzSkills 固有のドメイン用語 |
| DOC-context-constraints | [制約](00_はじめに/制約.md) | context | active | 0.1.0 | 変えられない前提・技術的／組織的制約 |
| DOC-context-stakeholders | [ステークホルダー](00_はじめに/ステークホルダー.md) | context | active | 0.1.0 | 関係者・想定利用者・アンチペルソナ |
| DOC-context-success-metrics | [成功指標](00_はじめに/成功指標.md) | context | active | 0.1.0 | North Star・入力指標・ガードレール指標 |
| DOC-context-personas | [ペルソナ・ジャーニー](00_はじめに/ペルソナ・ジャーニー.md) | context | active | 0.1.0 | 利用者像と体験の流れ |
| DOC-context-positioning | [ポジショニング](00_はじめに/ポジショニング.md) | context | active | 0.1.0 | 差別化の宣言と崩壊クリティカル仮説 |
| DOC-governance-overview | [ガバナンス](00_はじめに/ガバナンス.md) | governance | active | 0.1.0 | promotion gate・ADR基準・bump手順・ロードマップ意図 |
| DOC-system-overview | [システム仕様](01_システム仕様/システム仕様.md) | system | active | 0.1.0 | 機能・非機能・規約制約の人間向け索引 |
| DOC-usecase-index | [ユースケース一覧](02_ユースケース/ユースケース一覧.md) | usecase | active | 0.1.0 | UC-001〜 の索引と要件トレース |
| DOC-design-architecture | [アーキテクチャ](03_設計仕様/アーキテクチャ.md) | design | active | 0.1.0 | モノレポ構造・3プラットフォーム配布境界・依存方向 |
| DOC-design-domain-model | [ドメインモデル](03_設計仕様/ドメインモデル.md) | design | active | 0.1.0 | 中核概念と不変条件 |
| DOC-design-data-model | [データモデル](03_設計仕様/データモデル.md) | design | active | 0.1.0 | マニフェスト・frontmatter・観察ログの論理構造 |
| DOC-design-public-api | [公開APIと互換性](03_設計仕様/公開API.md) | design | active | 0.1.0 | **library 必須**: 公開面・互換性方針・support matrix |
| DOC-design-security-model | [セキュリティモデル](03_設計仕様/セキュリティモデル.md) | design | active | 0.1.0 | 信頼境界・脅威・ガードレール3層 |
| DOC-implementation-patterns | [実装パターン](03_設計仕様/実装パターン.md) | implementation | active | 0.1.0 | 恒久的な実装規約 |
| DOC-quality-testing | [テスト戦略](04_テスト仕様/テスト戦略.md) | quality | active | 0.1.0 | 検証3系統・品質ゲート・green の定義 |
| DOC-operations-overview | [運用・リリース](05_リリース・運用/運用・リリース.md) | operations | active | 0.1.0 | bump・リリース検証・配布・ロールバック |
| DOC-knowledge-lessons | [教訓](05_リリース・運用/教訓.md) | knowledge | active | 0.1.0 | 恒久的な教訓（LL-*） |
<!-- OPTIONAL_DOCUMENTS -->

### 決定記録 (ADR)

ADR は `03_設計仕様/意思決定/ADR-NNNN-<slug>.md`。現時点で採番済みの ADR は無い
（設計判断は `.spec/design/DSN-*` に記録されている。恒久化すべきものを ADR へ昇格させる）。

| ADR | タイトル | status |
|---|---|---|
| — | （未起票） | — |

## このツリーの読み方

規約は [`_conventions.md`](_conventions.md)、最小→最大規模の拡張と各層の docs↔.spec 境界は
[`_scaling.md`](_scaling.md) を参照。要点だけ再掲:

- `docs/` = 意図（WHY / 人間向け WHAT）。実行状態は持たない。
- `.spec/` = 検証可能な契約（EARS 要件）と実行状態。同じ事実が両方にあれば意図は docs、契約と状態は `.spec` が勝つ。
- `docs/` から `.spec/` へは一方向派生。閉じ戻し（昇格）は人間承認のみ。
- 新しい情報の置き場所は `_conventions.md` の Decision Matrix で決める。

## 管理対象外（excluded_paths）

以下は正式ナラティブではなく、検証済み調査記録・作業計画・旧ガイドとして併存する。

| パス | 位置づけ |
|---|---|
| `調査報告/` | Claude Code / Antigravity / Codex の一次資料に基づく検証済み仕様。プラットフォーム判断の根拠 |
| `翻訳規約/` | 翻訳作業用の規約メモ |

> 6章化以前の資料（`使い方ガイド.md` / `ユースケース.md` / 各種 master plan）は 2026-07-27 に削除した。
> ユースケースの内容は `02_ユースケース/ユースケース一覧.md` へ移してある。
