---
implements: [ENV-FR-010]
depends_on: [ENV-TSK-009]
boundary: plugins/bitz-env/skills/env-destroy/
status: done
---

### env-destroy スキルの新規作成

- **作業内容**: 新スキル env-destroy（SKILL.md）を作成する。
  レジストリの生成物トラッキング記録に基づき撤去対象一覧を提示し、ユーザー確認を得てから
  撤去する。既存ファイル（settings.json / AGENTS.md / CLAUDE.md）はマーカー区間のみ除去し、
  ユーザー自身の記述を保持する。レジストリが無い・記録が欠落している場合は推測で削除せず、
  検出できた候補の報告に留める。撤去対象はプロジェクト内限定（ENV-CON-003 と整合）。
- **備考**: frontmatter は spec.md 準拠（metadata 必須）。skill-validator のチェックを通すこと。
- **実施記録**: 2026-07-11 実施（v0.3.0）。SKILL.md 新規作成、README 収録スキル表へ行追加（boundary 外だが統合上必要な1行のみ）。release_check の frontmatter / validate は PASS。
