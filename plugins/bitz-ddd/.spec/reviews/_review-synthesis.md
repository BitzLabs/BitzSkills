---
view_of: DDD-REV-001
path: DDD-REV-001.md
updated: 2026-07-30
---

# 最新のレビュー統合結果（ビュー）

本ファイルは**最新レビューへの導線**であり、成果物そのものではない。自前の成果物 ID を
持たず、`_` 始まりのファイル名により `spec_inspect` のレジストリにも入らない（SDD-FR-160）。

- **最新**: [DDD-REV-001](DDD-REV-001.md) — bitz-ddd 設計レビュー統合レポート（requirements + discovery）（判定 CONDITIONAL_PASS）
- **機械可読**: [`DDD-REV-001.json`](DDD-REV-001.json)（ポインタは `review-synthesis.json`）

新しいレビューを記録するときは、**先に番号付きファイル `<REV-ID>.json` / `.md` を作成**し、
本ビューの `view_of` / `path` とリンクを差し替える。番号付きファイルが無いまま本ビューだけを
更新すると `spec_inspect` がアーカイブ漏れとして FAIL させる。
