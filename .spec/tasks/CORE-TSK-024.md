---
implements: CORE-FR-016
depends_on: [CORE-TSK-023]
boundary: plugins/bitz-sdd/skills/sdd-git/, plugins/bitz-sdd/**/plugin.json, plugins/bitz-sdd/skills/sdd-core/SKILL.md, plugins/bitz-sdd/skills/sdd-implement/, plugins/bitz-sdd/README.md, plugins/bitz-flow/README.md
status: done
---

### sdd-git の縮退と bitz-flow 依存宣言・参照更新

- **作業内容**: sdd-git SKILL.md を薄い委譲ポインタへ縮退（references 2件削除）、
  bitz-sdd 3マニフェストへ `metadata.dependencies: ["bitz-flow>=0.2"]` を宣言、
  参照元（sdd-core ルーティング表・sdd-implement 実装規律・両 README）の記述を bitz-flow 正へ更新。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
  boundary は着手時の見積り（parallel-git.md）から実態へ補正 — sdd-git への言及は
  parallel-git.md ではなく sdd-core/SKILL.md・README 側にあった。
