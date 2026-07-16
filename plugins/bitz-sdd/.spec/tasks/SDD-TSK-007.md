---
implements: SDD-FR-120, SDD-FR-121
depends_on: [SDD-TSK-005, SDD-TSK-006]
boundary: plugins/bitz-sdd/skills/sdd-core/SKILL.md, plugins/bitz-sdd/skills/sdd-report/SKILL.md, plugins/bitz-sdd/.claude-plugin/plugin.json, plugins/bitz-sdd/plugin.json, plugins/bitz-sdd/.codex-plugin/plugin.json
status: done
---

### sdd-core/sdd-report への責務境界・ルーティング追記とマニフェスト bump

- **作業内容**: ①sdd-core SKILL.md のフェーズ・ルーティング表に sdd-plan の行を追加し
  「現状把握・次アクション」のルーティング先を sdd-plan に一本化する。
  ②sdd-core の軽量レーン節に sdd-issue への参照・棲み分け（規律・ライフサイクルの正は sdd-core、
  インテーク運用フローは sdd-issue）を追記する。③sdd-report SKILL.md に sdd-plan との
  責務境界（人間向け成果文書の生成 vs セッション内対話ナビゲーション）を追記する。
  ④`scripts/bump_version.py bitz-sdd minor` で3マニフェストを同時 bump する（スキル2本追加のため minor）。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
