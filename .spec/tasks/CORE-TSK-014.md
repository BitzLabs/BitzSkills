---
implements: CORE-CON-008
depends_on: []
boundary: plugins/plugin-creator/skills/plugin-structure/references/lifecycle-skills.md, plugins/plugin-creator/.claude-plugin/plugin.json, plugins/plugin-creator/plugin.json, plugins/plugin-creator/.codex-plugin/plugin.json
status: done
---

### plugin-creator に標準ライフサイクルスキル reference を追加

- **作業内容**: `plugins/plugin-creator/skills/plugin-structure/references/lifecycle-skills.md`
  を新設し、標準スキル名 `<plugin名>:init` / `doctor` / `update` / `uninstall` の最小契約
  （init=初期設定と依存確認、doctor=環境診断・読み取り専用、update=バージョン更新と依存再確認、
  uninstall=痕跡を残さない撤去）を記述する。この4操作に該当しない独自スキルは従来の命名規則を
  維持してよい旨も明記する。plugin-structure の SKILL.md から本 reference への言及を追記する。
  最後に plugin-creator のバージョンを `scripts/bump_version.py plugin-creator patch` で bump する。
- **実施記録**: 2026-07-18 実施。release_check PASS・spec_inspect --workspace . plugins/* 全6ワークスペース PASS。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
