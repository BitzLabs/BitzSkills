---
id: SI-ENV-003
raised_by: sdd-review REV-001（operations OPS-201）
target: plugins/bitz-env/.spec/requirements/ENV-FR-003.md + skills/env-init/SKILL.md
proposed_change_type: bump
status: proposed
---
- **矛盾/曖昧の内容**: env-init は settings.json / AGENTS.md / CLAUDE.md をユーザー確認の
  うえ書き換えるが、書き込み後に元へ戻す手段（バックアップ・undo）が設計に無い。
  マージ判断を誤ると復旧はユーザーの git 頼みで、展開先が git 管理外だと復旧不能。
- **提案する修正**: いずれか、または併用。
  (a) 書き込み前に対象ファイルのバックアップ（.bak 保存 or 変更前 diff の記録）を取る手順を
      ENV-FR-003 の受入基準に追加。
  (b) 「展開先が git 管理下であること」を env-init の前提条件として明示し、
      未管理なら git init を先に案内する（ENV-FR-003 か新 CON）。
- **影響推定**: ENV-FR-003 に受入基準1〜2項追加、env-init/SKILL.md のワークフロー修正。
  ENV-CON-003（プロジェクト内書き込み限定）と整合。既存の生成挙動は保持したまま安全策を上乗せ。
