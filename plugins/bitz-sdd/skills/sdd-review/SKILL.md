---
name: sdd-review
description: BitzSDD の設計ドキュメントを多観点で並列レビューするスキル。consistency（構造・トレーサビリティ・用語）/ data-integrity（トランザクション・整合性・スキーマ）/ operations（監視・DR・デプロイ）/ risk（分散リスク・障害モード）/ business（要件トレース・NFR定量化）の観点別レビューを並列実行し、重複排除・P0〜P3分類・PASS/CONDITIONAL_PASS/FAIL の統合判定にまとめる。「設計をレビューして」「多観点レビュー」「設計の品質ゲート」「レビューを統合して」と言われたとき、sdd-design のドラフト完成時（Design Gate 前）、または Promotion Gate 前の docs/ 更新確認時に使用する。判定は人間ゲートへの推奨であり、承認・active 化は行わない。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-07-08"
---

# SDD Review — 多観点並列レビュー

設計ドキュメントの品質を観点別に並列レビューし、単一の統合判定にまとめる。bitz-sdd の「検証中心」（人間は行をレビューせず、ゲートと例外だけを見る）を設計ドキュメントに適用したもの。**判定は Design Gate / Promotion Gate への推奨であり、このスキルが承認や proposed→active 化を行うことはない。**

## レビュー対象の決め方

依頼に対象指定がなければ、次の順で収集する（存在するものだけ）:

1. `docs/02-design/**/*.md`（proposed ドラフトを含む。Design Gate 前の主対象）
2. `docs/01-context/**/*.md`（business 観点の照合元）
3. `.planning/requirements/*.md`・`.planning/specs/**/*.md`（トレーサビリティの照合元）

対象ファイル一覧（1行1パス）を確定してから観点を起動する。

## 実行手順

1. **レジストリ読み込み** — `assets/review-registry.json` を読む。プロジェクト側に `.planning/review/registry.json` があればそちらを優先する（重み・しきい値のプロジェクト調整用）
2. **観点の決定** — `conditions: always` の観点は常に有効。`persistent-data` の data-integrity は設計が永続データ（DB・ファイル・イベントストア等）を扱うときのみ有効
3. **並列起動** — 有効な観点ごとに `references/perspective-<name>.md` を読み、`{FILE_LIST}` を対象一覧に置換して**1観点=1サブエージェント**として1メッセージで並列起動する。サブエージェント機構が使えない環境では観点を1つずつ順に実行する（結果の書式は同一）
4. **結果保存** — 各観点の JSON を `.planning/review/individual/<perspective>.json` に保存する
5. **統合** — `references/synthesis.md` の手順で重複排除→P0〜P3 分類→重み正規化→ゲート判定を行い、`.planning/review/review-synthesis.json` と同 `.md`（書式は `assets/review-report.md`）を出力する

## 判定の扱い

- 統合レポートと判定（PASS / CONDITIONAL_PASS / FAIL）を人間に提示する。**裁定は人間**（Design Gate / Promotion Gate）
- CONDITIONAL_PASS の条件リストは STATE.md に転記し、消化を追跡する
- レビュー中に**要件そのものの矛盾・曖昧さ**を発見した場合は、finding にするだけでなく bitz-sdd の規律に従い `spec-issues/` に起票する（requirements/ は編集しない）
- 作業成果物（individual/ の JSON・統合レポート）は `.planning/review/` に置く。docs/ には書かない

## 連携

- 設計ドラフトの作成は `sdd-design`、上流探索は `sdd-discovery`、要件・ゲート運用は `bitz-sdd` の管轄
- Design Gate / Promotion Gate の位置づけは `bitz-sdd` スキル（ゲート規約）が正

## 出典

本スキルのレビュー観点・統合手順は [nexus-architect](https://github.com/wfukatsu/nexus-architect)（MIT License, Copyright (c) 2026 Wataru Fukatsu）の review-* スキル群から ScalarDB 固有部分を除いて翻案・圧縮したもの。
