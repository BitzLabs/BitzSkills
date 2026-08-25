# 最新レビュー統合報告（ビュー）

最新は **FLW-REV-029**（FAIL / 集計 2.72）。本文は FLW-REV-029.md を正とする。
本ファイルは最新へのポインタであり自前の ID を持たない。

- 判定: FAIL（前回 FLW-REV-028 v2.0 も FAIL 2.52）
- findings: P0 1 / P1 6 / P2 2 / P3 0
- risk 2.33 が floor 2.5 に未達（集計 2.72 は閾値超え）
- Gate blocking: GP-001〜GP-006（すべて basis: verified / response: accepted）
- セカンドオピニオン: codex（OpenAI）FAIL / antigravity（Gemini）追加欠陥6件。
  **統合判定より前に実施**
- 公開判断: 裁定記録の後退条件に該当（P0 が本公開に対して出た）。後退か前進かは人間裁定
