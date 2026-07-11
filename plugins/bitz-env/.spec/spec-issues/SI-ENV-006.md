---
id: SI-ENV-006
raised_by: sdd-review 第2ラウンド クロスモデル（agy/Gemini）AGY-7
target: plugins/bitz-env/skills/（新スキル env-destroy）+ ENV-DSN-001
proposed_change_type: new
status: accepted
---
- **矛盾/曖昧の内容**: フック（即効層）はプラグイン無効化で消えるが、env-init が生成した
  恒久層（settings.json の permissions・AGENTS.md / CLAUDE.md のマーカー区間・
  .claude/agents/ の advisor/worker）はアンインストール後も残り続ける。ユーザー環境に
  「原因不明の制限・記述」がサイレントに残留（ロックイン）する。REV-001 も見落とした
  ライフサイクル管理の欠落。
- **提案する修正**: env-init が生成物をトラッキングし（マーカー区間・生成ファイル一覧を
  レジストリに記録）、アンインストール/無効化時に安全にパージ・ロールバックする
  env-destroy（env-cleanup）スキルを機能要件として追加する。ENV-FR-009（生成前バックアップ）
  と対で設計し、パージもユーザー確認付き・マーカー区間のみ除去とする。
- **影響推定**: 新スキル env-destroy の追加（SKILL.md）。env-init に生成物トラッキングの
  受入基準追加。ENV-DSN-001 にライフサイクル節を追加。ENV-CON-003（プロジェクト内限定）と整合。
