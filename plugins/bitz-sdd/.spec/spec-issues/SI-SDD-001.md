---
id: SI-SDD-001
raised_by: sdd-core 準拠運用（bitz-sdd ワークスペース新設後の初回 sdd-report 実行で発見）
target: plugins/bitz-sdd/skills/sdd-report/scripts/sdd_report.py（要件走査）
proposed_change_type: bump
status: accepted
---
- **矛盾/曖昧の内容**: sdd_report.py は `.spec/requirements/` 配下の全 .md を要件として
  カウントするため、統制語彙ファイル `domains.md`（sdd-core が規定する非要件ファイル）を
  要件1件・status 不明 = draft として誤集計する。実要件31件・draft 0 の状態で
  「32件・Draft 1」と報告され、総合ヘルスが YELLOW（ドラフト状態の要件あり）に誤判定される。
- **提案する修正**: 要件走査から `domains.md` を除外する（または frontmatter に `id:` を
  持たないファイルを要件として数えない。spec_inspect.py の load_requirements と
  同じ判定基準に揃えるのが望ましい）。
- **影響推定**: sdd_report.py の要件スキャンのみ。カウント精度の修正で、
  既存レポートの他セクションへの影響なし。
- **裁定**: 2026-07-12 人間裁定により accepted 化（チャット指示）。提案どおり
  spec_inspect.py の load_requirements と同じ判定基準に揃える
  （`_` 始まり・`domains.md` を除外し、frontmatter に `id:` を持たないファイルは
  要件として数えない）。既存要件 SDD-FR-110/111 の範囲内のバグ修正のため
  新規要件は起票しない（軽量レーン）。
- **実施**: 2026-07-12 SDD-TSK-003 で修正・回帰テスト追加済み。
