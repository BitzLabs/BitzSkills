---
id: SI-ENV-010
raised_by: skill-evaluator（evals/env-init/report.md 改善提案3節）
target: plugins/bitz-env/skills/env-init/SKILL.md + references/permissions.md
proposed_change_type: bump
status: accepted
---
- **矛盾/曖昧の内容**: env-init が既存 .claude/settings.json の permissions
  （deny/ask）をテンプレートとマージする際、値が完全一致するエントリの重複は
  回避される実装になっているが（evals/env-init/runs/6 で確認: 既存の
  "Bash(git push:*)" とテンプレート側の同一値が1件に統合された）、値が完全一致
  しないが意味的に重複するエントリ（例: 表記ゆれ、パターンの包含関係）の扱いは
  SKILL.md に規定がない。runs/6 の log.md 備考で実行者自身が「判断が実行者依存に
  なる懸念がある」と自己申告している（evals/env-init/report.md 改善提案3節）。
- **提案する修正**: SKILL.md の permissions マージ手順に、意味的重複の判定規則を
  明記する。例: 「文字列を正規化（前後空白除去・大文字小文字統一等）した上で完全一致する
  もののみを重複とみなし、それ以外はパターンの包含関係を判定せず両方を残す
  （安全側に倒す＝多重登録を許容し、削除は行わない）」といった、npm publish や
  git push に限らない一般規則として記述する。過学習防止のため特定コマンド名は
  規則本文に含めない。
- **影響推定**: SKILL.md のマージ手順に規則1件を追記。実装（マージロジック）の
  正規化処理の追加が必要な場合がある。既存の受入基準（ENVFR003-S3: 既存エントリを
  削除しない）とは矛盾しない形で拡張する。
- **裁定記録**: 2026-07-12 人間裁定（チャット指示「残りのISSUEを進めましょう」）により accepted。提案どおり反映する（既存要件の範囲内の記述明確化のため新規要件は起票しない = 軽量レーン）。
- **実施**: 2026-07-12 対象 SKILL.md へ反映済み（スキル metadata version を patch bump）。
