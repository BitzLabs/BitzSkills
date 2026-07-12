---
id: SI-SDD-001
raised_by: sdd-core 準拠運用（bitz-sdd ワークスペース新設後の初回 sdd-report 実行で発見）
target: plugins/bitz-sdd/skills/sdd-report/scripts/sdd_report.py（要件走査）
proposed_change_type: bump
status: open
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
