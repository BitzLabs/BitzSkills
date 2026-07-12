---
id: DDD-DSC-003
title: "bitz-ddd スコープ（制約 → MoSCoW → In/Out-of-Scope 境界）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# スコープ（制約 → MoSCoW → In/Out-of-Scope 境界）

> 遡及 discovery。既にリリース済みの機能セットを MoSCoW で追認し、今後（特に SI-CORE-014）の
> 帯域を明示する。Out-of-Scope（Won't）リストがスコープクリープに対する主ガード。

## 制約の棚卸し（最初にやる）

| 種別 | 制約 |
|---|---|
| 技術 | bitz-sdd プラグイン必須（`.spec/design/` 契約・sdd-core artifact-frontmatter・DSN- 体系に依存）。単体動作しない |
| 技術 | 各スキルはフォルダ単位で自己完結（他スキルの references を相対参照しない。連携はスキル名の言及） |
| 技術 | 成果物の frontmatter 仕様は sdd-core 側が正。bitz-ddd 側で勝手に定義しない |
| 組織 | メンテナは実質1名（作者 hide）。運用・保守コストは1人分に収める |
| プロセス | 開発は sdd-core 準拠（ドッグフーディング）。適用する bitz-sdd はリリース済み版に固定（PROJECT.md） |
| 法規制 | Agent Skills オープン標準／OSS ライセンス準拠。特段の追加規制なし |

**スコープ項目は上記制約に違反してはならない。** 違反するものは Won't に落とす。

## MoSCoW（帯域分け）

現行リリース（v0.1.1）の機能を追認しつつ、今後の帯を分ける。判定基準:
「これ以外を全部出荷したら成功指標（DDD-DSC-002）を達成できるか?」

| 帯 | 項目 | 根拠 |
|---|---|---|
| **Must** | ddd-story（Domain Storytelling → `.spec/design/stories/`） | ドメインモデルと要件派生の根拠。DDD の入口。実装済み |
| **Must** | ddd-model（戦略/戦術設計・2パス導出必須 → `domain-model.md`） | プラグインの中核価値。実装済み |
| **Must** | bitz-sdd 契約準拠（artifact-frontmatter / DSN- 体系） | 併用前提が成立する条件。ガードレール G1 |
| **Should** | ddd-evaluate（DDD 12基準 + MMI 4軸のブラウンフィールド評価） | 既存コード向けで価値は高いが、グリーンフィールドでは無くても DDD は回る。実装済み |
| **Should** | 各スキルの references による progressive disclosure | 現状 references あり。品質保守に効くが機能の本質ではない |
| **Could** | SI-CORE-014: 3段階読み込み化 + 定型スクリプト化（mmi_score.py 等） | トークン削減・保守性向上の磨き込み。**構造/動作変更で内容は不変**。未着手（open・依存 013） |
| **Won't（今回は）** | イベントストーミングのワークショップ運用支援（複数人・付箋・リアルタイム協調） | AI 主導の軽量導出が前提。多人数ワークショップ機能はスコープ外 |
| **Won't（今回は）** | bitz-sdd 非依存の単体 DDD ツール化 | 併用前提が設計の核。独立化は Vision に反する |
| **Won't（今回は）** | コード自動生成（モデルからの実装スキャフォールド） | 設計手法プロバイダに徹する。実装は sdd-implement の管轄 |
| **Won't（今回は）** | ストレージ/DB スキーマ設計 | 「ドメインをモデル化する、DB スキーマをモデル化しない」原則。永続化は sdd-data の管轄 |
| **Won't（今回は）** | 非 DDD の設計手法（例: データフロー中心設計）の追加 | プラグインの焦点を DDD に限定 |

## In-Scope / Out-of-Scope 境界（必須）

| 区分 | 内容 |
|---|---|
| **In-Scope** | ドメインストーリー記述 / 戦略・戦術ドメインモデリング / ブラウンフィールド DDD・MMI 評価 / これらの成果物の `.spec/design/` への契約準拠書き込み |
| **Out-of-Scope（Won't）** | 多人数イベントストーミング運用 / 単体ツール化 / コード自動生成 / DB・ストレージ設計 / 要件・タスク・テスト・インフラ設計（各 sdd-* の管轄） / 非 DDD 設計手法 |

**Won't を名指しすることがスコープクリープを止める。** 特に「単体ツール化」と「コード自動生成」は
要望が来やすいが、Vision（SDD 契約準拠プロバイダ）を壊すため明示的に延期/除外する。
