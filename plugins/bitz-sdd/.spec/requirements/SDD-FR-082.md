---
id: SDD-FR-082
version: 1.0
status: draft
domain: execution
priority: medium
origin: skills/sdd-git/SKILL.md v0.1.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-082 タスク失敗時の worktree 破棄による復元

- **説明**: sdd-git はタスク失敗からの復元を行う際、破壊的操作（`git reset --hard` 等）を避け、現在の作業状態を worktree ごと破棄してタスクを再投入しなければならない。
- **受入基準 (EARS)**:
  - WHEN タスクが失敗してやり直しが必要になった THEN sdd-git は現在の worktree を破棄（`git worktree remove` + ブランチ削除）してタスクを再投入 SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.1.0 からの reverse-derived。ワークスペース新設に伴う逆起票）
