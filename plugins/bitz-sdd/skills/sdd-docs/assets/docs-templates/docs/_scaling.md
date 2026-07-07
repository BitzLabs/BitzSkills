<!--
  _scaling.md — 最小起動セットから「最大規模」までの docs/ 構成と拡張規約。
  最大規模で戻ってくる 03/04/05/07 は .planning/ と役割が重なりやすい「ドリフト危険地帯」。
  各層で「docs/ に何が残り、.planning/ に何が行くか」を必ず守ること。
-->
# docs/ スケーリング規約（最小 → 最大規模）

## 最大規模の全体構成

```
docs/
  MASTER.md                       索引・project_type 宣言
  _conventions.md                 frontmatter・ライフサイクル・配置ルール
  _scaling.md                     このファイル
  01-context/                     意図（WHY / 人間向け WHAT）— 最も遅く変わる
    mission-vision.md
    glossary.md
    non-goals.md
    constraints.md                技術的・組織的制約（旧 FeelFlow CONSTRAINTS）
    stakeholders.md               app: 関係者 / library: 想定コンシューマ像
  02-design/                      構造・設計判断
    ARCHITECTURE.md
    domain-model.md               ドメインモデル（旧 FeelFlow DOMAIN）
    public-api.md                 library 専用: 公開契約と互換性
    security-model.md             信頼境界・脅威・データ分類
    decisions/ADR-*.md            決定記録（不採用案・試行錯誤）
  03-implementation/              恒久的な実装規約（per-feature タスクは .planning/）
    PATTERNS.md
    error-handling.md
    dependency-policy.md
  04-quality/                     品質・検証の「戦略」（per-req 検証は .planning/）
    TESTING.md
    quality-gates.md
    performance-budgets.md
  05-operations/                  運用・リリースの恒久手順とポリシー
    OPERATIONS.md
    (app) runbooks/ , slo.md , incident-response.md
    (library) release-process.md , support-matrix.md , deprecation-calendar.md
  06-reference/                   外部参照・移行ガイド
    EXTERNAL-APIS.md
    migration/<version>.md
    integrations.md
  07-governance/                  プロセス・ロードマップの意図（実行は .planning/ROADMAP）
    GOVERNANCE.md
    contribution.md
    versioning-policy.md
  08-knowledge/                   恒久知識
    LESSONS_LEARNED.md
    postmortems/<date>-<slug>.md
```

## ドリフト危険地帯（03 / 04 / 05 / 07）の境界規則

これらは `.planning/` に鏡像がある。**同じ名前でも中身の粒度が違う**。判定は一つ:

> **フィーチャ／スプリントごとに変わるなら `.planning/`。フィーチャを越えて残る標準・方針なら `docs/`。**

| 層 | `docs/`（恒久・方針・WHY） | `.planning/`（使い捨て・実行・状態） |
|---|---|---|
| 03-implementation | コーディング規約・採用パターン・命名・エラー方針 | フィーチャ単位の実装タスク・依存グラフ (tasks/) |
| 04-quality | テスト戦略・「緑」の定義・品質ゲートの意味 | 要件別の verification_method・PBT マッピング (specs/) |
| 05-operations | リリース手順・ランブック・SLO 方針・非推奨カレンダー | リリース回ごとのチェックリスト・実行状態 (STATE) |
| 07-governance | プロセス規約・バージョニング方針・ロードマップの意図 | 実行可能なロードマップ・マイルストーン (ROADMAP) |

同じ事実が両方に出たら、**方針は docs/、実行と状態は .planning/ が勝つ**。

## 段階拡張のトリガー（増やしすぎない）

| 追加する層 | 追加の合図 |
|---|---|
| 起点: 01 / 02 / 08（library は +public-api） | プロジェクト開始時 |
| 03-implementation | 実装パターンが繰り返し現れ、標準化する価値が出たとき |
| 04-quality | テスト戦略を feature を越えて共有・強制したくなったとき |
| 05-operations | 定期的にデプロイ／公開し、再現可能な手順が要るとき |
| 06-reference | 外部 API に依存、または破壊的変更で移行ガイドが要るとき |
| 07-governance | 貢献者が増え、プロセスとロードマップの明文化が要るとき |

> 原則: **空フォルダを先に切らない**。必要になった層だけを、その時点で MASTER.md の
> レジストリに登録して足す。AI ツールは情報の散在に弱いので、密度を保つことが精度に効く。

## app / library での重みの違い

- **app**: 05-operations が厚くなる（デプロイ・SLO・インシデント・オンコール）。
  02 に data-model / security-model が効く。
- **library**: 02-design/public-api と 05-operations/release-process・support-matrix・
  deprecation-calendar が中核。07 の versioning-policy が SemVer 契約と直結する。
  逆にランタイム運用系（SLO・オンコール）は基本不要。
