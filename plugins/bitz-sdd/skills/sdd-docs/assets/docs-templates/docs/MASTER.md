---
id: DOC-master
title: <Project Name> — Documentation Index
status: active
version: 0.1.0
changeImpact: low
project_type: both            # app | library | both。プロジェクト全体の種別
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null
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
| ★ DOC-context-mission | [Mission & Vision](01-context/mission-vision.md) | context | active | 0.1.0 | 目的とゴール |
| ★ DOC-context-glossary | [Glossary](01-context/glossary.md) | context | active | 0.1.0 | ドメイン用語 |
| ★ DOC-context-non-goals | [Non-Goals](01-context/non-goals.md) | context | active | 0.1.0 | やらないことの境界 |
| DOC-context-constraints | [Constraints](01-context/constraints.md) | context | active | 0.1.0 | 変えられない前提・制約 |
| DOC-context-stakeholders | [Stakeholders / Consumers](01-context/stakeholders.md) | context | active | 0.1.0 | 関係者 / 想定コンシューマ |
| DOC-context-success-metrics | [Success Metrics](01-context/success-metrics.md) | context | proposed | 0.1.0 | NSM・入力指標・ガードレール（sdd-discovery 使用時） |
| DOC-context-personas | [Personas & Journeys](01-context/personas-journeys.md) | context | proposed | 0.1.0 | ペルソナ・ジャーニー（sdd-discovery 使用時） |
| DOC-context-positioning | [Positioning](01-context/positioning.md) | context | proposed | 0.1.0 | 差別化の宣言（sdd-discovery 使用時） |
| ★ DOC-design-architecture | [Architecture](02-design/ARCHITECTURE.md) | design | active | 0.1.0 | 構造と境界 |
| DOC-design-domain-model | [Domain Model](02-design/domain-model.md) | design | active | 0.1.0 | 中核概念と不変条件 |
| ☆ DOC-design-public-api | [Public API & Compatibility](02-design/public-api.md) | design | active | 0.1.0 | **library 専用**: 公開面と互換性 |
| DOC-design-security-model | [Security Model](02-design/security-model.md) | design | active | 0.1.0 | 信頼境界・脅威・データ分類 |
| DOC-implementation-patterns | [Implementation Patterns](03-implementation/PATTERNS.md) | implementation | active | 0.1.0 | 恒久的な実装規約 |
| DOC-quality-testing | [Testing Strategy](04-quality/TESTING.md) | quality | active | 0.1.0 | テスト戦略・緑の定義 |
| DOC-operations-overview | [Operations & Release](05-operations/OPERATIONS.md) | operations | active | 0.1.0 | 運用・リリース手順 |
| DOC-reference-external-apis | [External APIs & References](06-reference/EXTERNAL-APIS.md) | reference | active | 0.1.0 | 外部依存・移行ガイド |
| DOC-governance-overview | [Governance](07-governance/GOVERNANCE.md) | governance | active | 0.1.0 | プロセス・方針・ロードマップ意図 |
| ★ DOC-knowledge-lessons | [Lessons Learned](08-knowledge/LESSONS_LEARNED.md) | knowledge | active | 0.1.0 | 恒久的な教訓 |

★ = 最小起動セット / ☆ = library では起動時から必須

<!-- ADR は decisions/ 配下。件数が増えるので下に別表を持つ。 -->

### 決定記録 (ADR)

| ADR | タイトル | status |
|---|---|---|
| [ADR-0001](02-design/decisions/ADR-0001-<slug>.md) | <決定タイトル> | accepted |

## このツリーの読み方

規約は [`_conventions.md`](_conventions.md)、最小→最大規模の拡張と各層の docs↔.spec 境界は
[`_scaling.md`](_scaling.md) を参照。要点だけ再掲:

- `docs/` = 意図（WHY / 人間向け WHAT）。実行状態は持たない。
- 新しい情報の置き場所は `_conventions.md` の Decision Matrix で決める。
- `docs/` から `.spec/` へは一方向派生。閉じ戻しは人間承認のみ。

<!-- 最小起動セット: MASTER + mission-vision + glossary + non-goals + ARCHITECTURE + LESSONS。
     library はこれに public-api を必須で加える。成長したら 06-reference/ 等を足す。 -->
