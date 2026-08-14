---
id: QLT-DSC-003
title: "bitz-quality レビュー基盤 制約"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# 制約

- Python 3.10+標準ライブラリを機械検査の既定とし、LLM実行自体はplatform adapterへ隔離する。
- Agent Skills準拠のスキル単体配布で壊れない自己完結性を保つ。
- Claude/Codex/Antigravityで利用できない固有機能は必須の論理契約へ含めない。
- `sdd-review`の既存`ReviewFinding`、`gate_preconditions`、verdict語彙を移管canaryの互換基準にする。
- 既存レビュー成果物は上書き・一括変換・削除しない。
- status変更、GatePassage、canonical verification evidenceはbitz-sdd、Git/PR副作用はbitz-flowが所有する。
- 人間裁定前にspec-issueをaccepted、要件をapprovedへ遷移させない。
