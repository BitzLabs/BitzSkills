---
implements: CORE-FR-014
depends_on: [CORE-TSK-017]
boundary: plugins/bitz-flow/skills/**
status: implementing
---

### sdd-git 内容の汎用化転記（flow-core / flow-worktree / flow-pr）

- **作業内容**: sdd-git（SKILL.md + references/worktree-operations.md + references/issue-driven-flow.md）
  の規定内容を SDD 非依存の表現に汎用化し、`flow-core`（フロー選択・ブランチ規約・コミット規定・
  失敗時復元）/ `flow-worktree`（worktree 定型手順・並列度管理）/ `flow-pr`（Issue 駆動 +
  Draft PR + squash merge + 未マージ依存の原則）の3スキルとして転記する。SDD 固有の接続点
  （Implements フッター・`.spec/tasks` 連携・spec-issue 対応表・parallel-git.md への委譲）は
  各スキル末尾の「bitz-sdd 併用時」節に隔離する。sdd-git 本体は無変更。司令塔が直接実施
  （判断を伴う汎用化のため委譲しない）。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
