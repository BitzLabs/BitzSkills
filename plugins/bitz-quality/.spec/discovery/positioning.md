---
id: QLT-DSC-006
title: "bitz-quality レビュー基盤 ポジショニング"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# ポジショニング

| 代替 | 強み | 不足 |
|---|---|---|
| モデルへの自由形式レビュー依頼 | 柔軟・即時 | schema、再現性、追跡、Gate契約がない |
| 現行`quality-review` | 再発防止loopを持つ | 論理Reviewer・platform adapter・成果物schemaが未確定 |
| 現行`sdd-review` | 5観点と成熟したsynthesis契約 | SDD固有で、汎用QA providerとして独立していない |
| CI静的解析 | 決定的・高速 | 仕様・設計・ビジネス観点を扱いにくい |

bitz-qualityは「LLMレビューを呼ぶ道具」ではなく、**レビュー活動をversion付き契約・測定・追跡へ変換する
QA provider**として位置づける。SDDとFlowはconsumerであり、qualityがそれらのSSOTを奪わない点を差別化する。
