---
name: sdd-review
description: BitzSDD の設計ドキュメントや要件定義を多観点（consistency/data-integrity/operations/risk/business）で並列レビューするスキル。結果はすべて .spec/reviews/ 配下に格納し、レポート自動生成およびゲート判定の材料とする。ユーザーが「設計レビュー」「要件レビュー」「多観点レビュー」に言及したとき、または Design Gate 前に使用する。
metadata:
  version: "0.5.0"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-08-13"
---

# SDD Review — 多観点並列レビュー

BitzSDDの設計と仕様の検証レビューを担当します。
`.spec/` ディレクトリに直接作成された仕様や設計（requirements, design）を対象にレビューを行い、その結果（PASS/CONDITIONAL_PASS/FAIL）を `.spec/reviews/` に格納します。

## 1. レビュー対象の決定
対象指定がない場合は、以下の優先順位で `.spec/` 配下から収集します：
1.  `.spec/design/**/*.md` (ドメインモデル、API、アーキテクチャ設計)
2.  `.spec/requirements/**/*.md` (機能・非機能要件)
3.  `.spec/discovery/**/*.md` (ディスカバリー成果物、business 観点の照合用)

## 2. 実行手順
1.  **レジストリ読み込み**: `assets/review-registry.json` を読み込む。プロジェクト側に `.spec/reviews/registry.json` があればそちらを優先。
2.  **並列起動**: 有効な観点ごとに `references/perspective-<name>.md` に従い、対象一覧に対するレビューを実行する。サブエージェントが利用できる場合は並列実行、それ以外は順次実行。
3.  **個別結果の保存**: 各観点の判定結果を `.spec/reviews/individual/<perspective>.json` に保存。
4.  **統合判定 (synthesis)**: **まず `spec_scaffold.py` の `review` 種別で雛形を作る**
    （`python3 <sdd-core スキル>/scripts/spec_scaffold.py <ws> review --prefix <REV接頭辞> --title T --owner <担当> [--findings N] [--preconditions N]`）。
    必須キーが最初から入るため、書いた後に `spec_inspect` で弾かれる手戻りを避けられる（SDD-FR-167）。
    そのうえで重複排除、P0〜P3 分類、重み正規化を行い、`.spec/reviews/<REV-ID>.json`（`schema_version: 2`）および統合報告書 `.spec/reviews/<REV-ID>.md` を**番号付きで**生成する。過去レビューの未消化 P0/P1 を `carried_over[]` へ取り込む。schema の正は `references/synthesis.md`。
5.  **ビューの差し替え**: `review-synthesis.json` と `_review-synthesis.md` を 4 で作った番号付きファイルへのポインタとして更新する。Markdown 側は `_` 始まりにして成果物の走査から外す。**順序を逆にしない** — 番号付きファイルが無いまま更新すると `spec_inspect` がアーカイブ漏れとして FAIL させる。

## 3. 判定結果の扱いとライフサイクル
*   判定（`PASS` / `CONDITIONAL_PASS` / `FAIL`）は `sdd-report` による自動集計の対象となり、統合進捗レポート `.spec/reports/status-report.md` に反映されます。
*   `FAIL` または `CONDITIONAL_PASS` の場合は、指摘事項を修正するか、条件を消化するまで Design Gate / Promotion Gate を通過することはできません。
*   レビューで見つかった要件や設計の根本的な問題は、`.spec/spec-issues/` に起票します。
*   **未紐づけの P0/P1 がある状態で `verdict: PASS` を出せません**（SDD-FR-159）。`findings[]` の `tracked_by` は spec-issue ID または `<REV-ID>:GP-NNN` を指し、実在検査の対象です。`gate_preconditions[]` は `kind`（`blocking` / `agenda`）と `basis`（`verified` / `assumed`）を必須とし、**`basis: assumed` を根拠に `kind: blocking` は立てられません**（SDD-FR-161）。新規 GP は `gp_kind`（`behavioral` / `artifact` / `process`）で分類し、`behavioral` に限って `ears` を必須とします（SI-SDD-042）。
*   分類済みの blocking GP は `response` を必須とし、`accepted` / `rejected` / `deferred` のいずれかで応答します。`original` はGP原文との逐語一致が必要です。却下には理由と再レビュー、延期には追跡先・期限・再判定Gateが必要です（SI-SDD-042）。
*   **ID体系**: 統合報告書 (`<REV-ID>.md`) は `REV-NNN` のIDを持ち、YAML frontmatterを含みます。`_review-synthesis.md` は最新へのビューであり自前の ID を持ちません。finding ID は `<REV-ID>:SYN-NNN` としてレビュー横断で一意にします。frontmatter には共通キーに加えて **`decision: PASS | CONDITIONAL_PASS | FAIL` を必須**で含めます（`sdd-report` の自動集計が参照する。書式の正は `sdd-core` の assets/artifact-frontmatter.md「領域固有の追加キー」）。Consistency観点の指摘事項は、制約要件(CON)との衝突を避けるため `RVC-` プレフィックスを使用します。
