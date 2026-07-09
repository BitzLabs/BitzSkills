---
name: sdd-discovery
description: BitzSDD の上流探索（ディスカバリー）を行うスキル。プロダクトビジョン（Vision Board / PR-FAQ）・成功指標（North Star Metric）・スコープ（MoSCoW / RICE）・ペルソナとジャーニー（JTBD）・ポジショニングを順に確立し、仮説検証ゲート（Go / No-Go）で設計着手可否を裁定する。成果物はすべて .spec/discovery/ 配下に作成し、docs/01-context/ へは sdd-docs の pull コマンドを用いて同期・展開する。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-07-09"
---

# SDD Discovery — 上流探索

BitzSDDにおける上流探索フェーズを担当します。
「なぜ作るか・誰のためか・何をやらないか」を定義したマスターファイルを `.spec/discovery/` 内に記述・検証し、最終的に `sdd-docs` スキルの同期（pull）機能で `docs/01-context/` へ展開します。

## 1. 前提
*   作業台帳は `assets/discovery-worksheet.md` をコピーして `.spec/discovery/worksheet.md` として使用します。
*   成果物は直接 `docs/` に書くのではなく、`.spec/discovery/` 内のファイルとして作成・修正します。

## 2. 絶対規則
*   **事実をでっち上げない**: 根拠のないターゲット数値・ペルソナの感情・競合情報は `TBD` または `[proto / 未検証]` と明示します。
*   上流探索で得られた結論やスコープのマスターは、`.spec/discovery/` 内に保存します。
*   **ID体系とFrontmatter**: マスターファイルは `DSC-NNN` のIDを持ち、必ず共通のYAML frontmatterを含めて作成します。

## 3. ワークフロー（6ステップ）

| # | ステップ | 成果物（マスターファイル） | docs/ 同期先 |
|---|---|---|---|
| 1 | ビジョン（Vision Board + PR-FAQ 圧力試験） | `.spec/discovery/vision.md` | `docs/01-context/mission-vision.md` |
| 2 | 成功指標（NSM + 入力指標 + ガードレール） | `.spec/discovery/metrics.md` | `docs/01-context/success-metrics.md` |
| 3 | スコープ（制約 → Kano → RICE → MoSCoW） | `.spec/discovery/scope.md` | `docs/01-context/non-goals.md` / `constraints.md` |
| 4 | ペルソナとジャーニー（JTBD → カード） | `.spec/discovery/personas.md` | `docs/01-context/personas-journeys.md` |
| 5 | ポジショニング（競合代替 → PoD/PoP） | `.spec/discovery/positioning.md` | `docs/01-context/positioning.md` |
| 6 | 仮説検証ゲート（Go / No-Go 裁定） | `.spec/discovery/assumptions.md` | - (レビュー/レポート集計対象) |

各ステップの完了後、`python3 scripts/sdd_sync.py pull` を実行して `docs/` ディレクトリにドキュメントとして展開します。

## 4. Discovery Gate（人間裁定）
ステップ6の判定材料（仮説一覧・テスト結果・未検証の崩壊クリティカル仮説）を揃えて人間に提示します。
*   **Go**: 崩壊クリティカルな仮説がすべて「検証済み」または「テスト+事前閾値が定義済み」。`sdd-design` フェーズへ進む。
*   **No-Go / Pivot**: 崩壊クリティカルな仮説が未検証かつテスト未定義。設計に進まず、ビジョン/スコープ設計に戻る。

判定結果は `.spec/discovery/assumptions.md` に判定エビデンスとともに記録されます。
