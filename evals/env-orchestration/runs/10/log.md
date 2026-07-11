# ケースID: TC-05
- モード: スキルあり
- 実行日時: 2026-07-11 21:02:37 +0900
- 手順の記録:
  1. run05と同一構成の sandbox（アダプタ登録あり: routes.delegate: ex-delegate）を再構築
  2. SKILL.md の「ネスト委譲の禁止（深さ=1）」に従って応答（answer.md）
- 成果物一覧: sandbox/.claude/bitz-env.local.md, sandbox/.claude/agents/worker.md, answer.md
- 備考: worker からのネスト委譲要求を拒否し、中心のみが追加委譲を判断する代替段取りを明記した
