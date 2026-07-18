---
implements: SDD-FR-122
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-implement/SKILL.md, plugins/bitz-sdd/.claude-plugin/plugin.json, plugins/bitz-sdd/plugin.json, plugins/bitz-sdd/.codex-plugin/plugin.json
status: done
---

### accepted spec-issue着手前の起票時前提再検証を明文化

- **作業内容**: `sdd-implement` の実行手順先頭に、accepted spec-issue の対象ファイル・件数・
  書式を現状と照合する「起票時前提の再検証」を追加する。趣旨を変えない乖離は要件の
  Revision History に補正理由を残し、趣旨を変える乖離は実装せず人間の再裁定へ戻す分岐を
  明記する。スキルの metadata と bitz-sdd の3マニフェストを patch bump する。
- **実施記録**: 2026-07-18 実施。skill-validator 全項目 PASS、release_check PASS、
  pytest 165件 green、spec inspect 全ワークスペース PASS。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
