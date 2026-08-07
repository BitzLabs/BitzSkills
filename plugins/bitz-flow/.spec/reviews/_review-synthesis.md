---
view_of: FLW-REV-006
path: FLW-REV-006.md
updated: 2026-08-07
---

# 最新のレビュー統合結果（ビュー）

本ファイルは**最新レビューへの導線**であり、成果物そのものではない。自前の成果物 ID を
持たず、`_` 始まりのファイル名により `spec_inspect` のレジストリにも入らない（SDD-FR-160）。

- **最新**: [FLW-REV-006](FLW-REV-006.md) — M0 eval 測定系の多観点レビュー（判定 **FAIL**、集計 2.42）
- **機械可読**: [`FLW-REV-006.json`](FLW-REV-006.json)（ポインタは `review-synthesis.json`）
- **前回**: [FLW-REV-002](FLW-REV-002.md) — bitz-flow v2 多観点設計レビュー（判定 PASS）

新しいレビューを記録するときは、**先に番号付きファイル `<REV-ID>.json` / `.md` を作成**し、
本ビューの `view_of` / `path` とリンクを差し替える。番号付きファイルが無いまま本ビューだけを
更新すると `spec_inspect` がアーカイブ漏れとして FAIL させる。
