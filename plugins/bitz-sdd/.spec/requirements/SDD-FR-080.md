---
id: SDD-FR-080
version: 1.0
status: approved
domain: execution
priority: medium
origin: skills/sdd-git/SKILL.md v0.1.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-080 複数エージェント並列開発時の worktree 隔離

- **説明**: sdd-git は複数のエージェントによる並列開発において、リポジトリへの競合や破壊を避けるため、1エージェントにつき1つの worktree とブランチを割り当てる隔離体制を構築しなければならない。
- **受入基準 (EARS)**:
  - WHEN 複数エージェントで並列開発を行う THEN sdd-git は 1エージェント = 1 worktree = 1ブランチ の体制を構築 SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.1.0 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
