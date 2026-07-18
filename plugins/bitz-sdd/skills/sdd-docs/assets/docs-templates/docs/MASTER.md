---
id: DOC-master
title: <プロジェクト名> — 文書索引
status: active
version: 0.1.0
changeImpact: low
project_type: both            # app | library | both。プロジェクト全体の種別
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null
optional_chapters:             # reference を宣言した場合だけ 06_リファレンス/ を追加
excluded_paths:                # カンマ区切りの docs/ 相対パス。例: 調査報告, archive
---

<!--
  MASTER.md は docs/ の索引兼ルーター。人が最初に開く1枚。
  - プロジェクト種別 (app/library) をここで宣言する（下流テンプレの分岐の基準）。
  - 文書の追加・状態変更のたびにこの表を更新する。
  - 索引以上の内容（設計・背景）はここに書かない。各文書へリンクするだけ。
-->

# <Project Name>

> 一文サマリ: <このプロジェクトが何であるか。library なら「誰の何を解決する API か」、app なら「誰の何を解決するプロダクトか」>

- **種別**: `<app | library>`
- **主要技術**: <C# / TypeScript(Web) / Rust など>
- **配布形態**: <library の場合: NuGet / npm / crates.io。app の場合: デプロイ先>
- **正 (source of truth)**: 意図=このツリー / 契約・状態=`.spec/`

## 文書レジストリ

<!--
  最小起動時は ★ の行だけで開始し、成長に応じて他行を有効化する。
  拡張の合図と各層の docs↔.spec 境界は _scaling.md を参照。
-->

| id | 文書 | area | status | version | 概要 |
|---|---|---|---|---|---|
| ★ DOC-context-mission | [ミッション・ビジョン](00_はじめに/ミッション・ビジョン.md) | context | active | 0.1.0 | 目的とゴール |
| ★ DOC-context-glossary | [用語集](00_はじめに/用語集.md) | context | active | 0.1.0 | ドメイン用語 |
| ★ DOC-context-non-goals | [対象外](00_はじめに/対象外.md) | context | active | 0.1.0 | やらないことの境界 |
| DOC-context-constraints | [制約](00_はじめに/制約.md) | context | active | 0.1.0 | 変えられない前提・制約 |
| DOC-context-stakeholders | [ステークホルダー](00_はじめに/ステークホルダー.md) | context | active | 0.1.0 | 関係者・想定利用者 |
| DOC-context-success-metrics | [成功指標](00_はじめに/成功指標.md) | context | proposed | 0.1.0 | NSM・入力指標・ガードレール |
| DOC-context-personas | [ペルソナ・ジャーニー](00_はじめに/ペルソナ・ジャーニー.md) | context | proposed | 0.1.0 | 利用者像と体験の流れ |
| DOC-context-positioning | [ポジショニング](00_はじめに/ポジショニング.md) | context | proposed | 0.1.0 | 差別化の宣言 |
| DOC-governance-overview | [ガバナンス](00_はじめに/ガバナンス.md) | governance | active | 0.1.0 | プロセス・方針・ロードマップ意図 |
| DOC-system-overview | [システム仕様](01_システム仕様/システム仕様.md) | system | active | 0.1.0 | 機能・非機能・制約の人間向け索引 |
| DOC-usecase-index | [ユースケース一覧](02_ユースケース/ユースケース一覧.md) | usecase | proposed | 0.1.0 | 利用シナリオの索引 |
| ★ DOC-design-architecture | [アーキテクチャ](03_設計仕様/アーキテクチャ.md) | design | active | 0.1.0 | 構造と境界 |
| DOC-design-domain-model | [ドメインモデル](03_設計仕様/ドメインモデル.md) | design | active | 0.1.0 | 中核概念と不変条件 |
| DOC-design-data-model | [データモデル](03_設計仕様/データモデル.md) | design | active | 0.1.0 | 論理データ構造 |
| ☆ DOC-design-public-api | [公開APIと互換性](03_設計仕様/公開API.md) | design | active | 0.1.0 | **library 専用**: 公開面と互換性 |
| DOC-design-security-model | [セキュリティモデル](03_設計仕様/セキュリティモデル.md) | design | active | 0.1.0 | 信頼境界・脅威・データ分類 |
| DOC-implementation-patterns | [実装パターン](03_設計仕様/実装パターン.md) | implementation | active | 0.1.0 | 恒久的な実装規約 |
| DOC-quality-testing | [テスト戦略](04_テスト仕様/テスト戦略.md) | quality | active | 0.1.0 | テスト戦略・greenの定義 |
| DOC-operations-overview | [運用・リリース](05_リリース・運用/運用・リリース.md) | operations | active | 0.1.0 | 運用・リリース手順 |
| ★ DOC-knowledge-lessons | [教訓](05_リリース・運用/教訓.md) | knowledge | active | 0.1.0 | 恒久的な教訓 |
<!-- OPTIONAL_DOCUMENTS -->

★ = 最小起動セット / ☆ = library では起動時から必須

<!-- ADR は decisions/ 配下。件数が増えるので下に別表を持つ。 -->

### 決定記録 (ADR)

| ADR | タイトル | status |
|---|---|---|
| [ADR-0001](03_設計仕様/意思決定/ADR-0001-<slug>.md) | <決定タイトル> | accepted |

## このツリーの読み方

規約は [`_conventions.md`](_conventions.md)、最小→最大規模の拡張と各層の docs↔.spec 境界は
[`_scaling.md`](_scaling.md) を参照。要点だけ再掲:

- `docs/` = 意図（WHY / 人間向け WHAT）。実行状態は持たない。
- 新しい情報の置き場所は `_conventions.md` の Decision Matrix で決める。
- `docs/` から `.spec/` へは一方向派生。閉じ戻しは人間承認のみ。

<!-- 必須6章は常に維持する。library は公開APIを必須とする。
     参照資料が増えた場合だけ optional_chapters: reference と 06_リファレンス/ を追加する。 -->
