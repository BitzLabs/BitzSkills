---
implements: SDD-FR-001
depends_on: []
boundary: skills/sdd-core/SKILL.md,skills/sdd-core/scripts/spec_inspect.py,tests/test_spec_inspect.py,.claude-plugin/plugin.json,.codex-plugin/plugin.json,plugin.json
status: done
---

### 複数workspaceのタスクIDを既知化する

- **作業内容**: 複数 workspace 検査時に全対象 workspace のタスク ID を集約し、
  クロス workspace の実在タスク参照を幽霊判定から除外する。単一 workspace と
  存在しないタスク参照の判定を維持する回帰テストを追加する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
