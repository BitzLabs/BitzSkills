---
implements: DDD-FR-001
depends_on: []
boundary: plugins/bitz-ddd/ 配下のみ
status: done
---

### ddd-doctor 環境診断スキルの新規作成と bitz-sdd 依存宣言

- **作業内容**:
  - ddd-doctor スキル新規作成（`plugins/bitz-ddd/skills/ddd-doctor/SKILL.md`）。読み取り専用の環境診断スキルとし、
    (a) 依存プラグイン bitz-sdd の有効性・semver 制約充足の診断、(b) 利用プロジェクトの `.spec/design/` 存在時の
    `.spec/` ワークスペース前提の診断、(c) 全て OK の場合の OK 判定と根拠報告、を行う
  - 3マニフェスト（`.claude-plugin/plugin.json` / `plugin.json` / `.codex-plugin/plugin.json`）へ
    `metadata.dependencies: ["bitz-sdd>=2.0"]` を追加
  - version bump（bitz-ddd, minor）
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
