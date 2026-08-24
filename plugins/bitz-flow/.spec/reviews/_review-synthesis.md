# 最新レビュー統合報告（ビュー）

最新は **FLW-REV-028 v2.0**（FAIL / 集計 2.52）。本文は FLW-REV-028.md を正とする。
本ファイルは最新へのポインタであり自前の ID を持たない。

- 判定: FAIL（v1.0 の CONDITIONAL_PASS 3.75 から訂正。前回 FLW-REV-027 も FAIL 2.12）
- findings: P0 1 / P1 8 / P2 3 / P3 0
- risk 2.00 が floor 2.5 に未達
- Gate blocking: GP-001〜GP-008（すべて basis: verified / response: accepted）
- セカンドオピニオン: codex（OpenAI）FAIL / antigravity（Gemini）追加欠陥6件
- 公開判断: worktree operation は gated を維持
