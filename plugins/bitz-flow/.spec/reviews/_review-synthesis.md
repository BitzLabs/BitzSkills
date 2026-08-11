---
view_of: FLW-REV-007
path: FLW-REV-007.md
updated: 2026-08-11
---

# 最新のレビュー統合結果（ビュー）

本ファイルは**最新レビューへの導線**であり、成果物そのものではない。自前の成果物 ID を
持たず、`_` 始まりのファイル名により `spec_inspect` のレジストリにも入らない（SDD-FR-160）。

- **最新**: [FLW-REV-007](FLW-REV-007.md) — 全採点proxy棚卸し設計レビュー（判定 **PASS**、集計 4.88）
- **機械可読**: [`FLW-REV-007.json`](FLW-REV-007.json)（ポインタは `review-synthesis.json`）
- **前回**: [FLW-REV-006](FLW-REV-006.md) — M0 eval 測定系の多観点レビュー（判定 FAIL）

新しいレビューを記録するときは、**先に番号付きファイル `<REV-ID>.json` / `.md` を作成**し、
本ビューの `view_of` / `path` とリンクを差し替える。番号付きファイルが無いまま本ビューだけを
更新すると `spec_inspect` がアーカイブ漏れとして FAIL させる。
