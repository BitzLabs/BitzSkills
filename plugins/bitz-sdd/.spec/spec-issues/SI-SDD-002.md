---
id: SI-SDD-002
raised_by: sdd-core 準拠運用（bitz-sdd ワークスペース新設後の初回 sdd-report 実行で発見）
target: plugins/bitz-sdd/skills/sdd-report/scripts/sdd_report.py（要件タイトル抽出）
proposed_change_type: bump
status: open
---
- **矛盾/曖昧の内容**: sdd_report.py は要件タイトルを frontmatter の `title:` から
  読もうとするが、要件ファイルの公開契約書式（artifact-frontmatter.md / 既存の
  CORE-* / ENV-* / SDD-* 全要件）にはそもそも `title:` フィールドが存在せず、
  タイトルは本文見出し `### <ID> <タイトル>` が正。結果、レポートの要件一覧が
  全行「No Title」になり、一覧としての用をなさない。
- **提案する修正**: 本文の最初の `### <ID> <タイトル>` 見出しから ID 以降を
  タイトルとして抽出する（frontmatter `title:` があればそちらを優先してもよい）。
- **影響推定**: sdd_report.py のタイトル抽出のみ。表示改善で判定ロジックへの影響なし。
