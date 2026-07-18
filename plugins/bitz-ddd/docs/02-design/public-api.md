---
id: DOC-design-public-api
title: "Public API & Compatibility"
status: proposed
version: 0.1.0
changeImpact: low
project_type: library
updated: 2026-07-18
owner: hide
superseded_by: null
---

# Public API & Compatibility

公開面は次の配布物である。

- `skills/ddd-story/SKILL.md` と同梱 assets/references
- `skills/ddd-model/SKILL.md` と同梱 references
- `skills/ddd-evaluate/SKILL.md` と同梱 assets/references
- 3プラットフォーム向けプラグインマニフェスト

互換性は各 SKILL.md の frontmatter version とプラグインの3マニフェストに対する SemVer で管理する。破壊的変更は major、後方互換な追加は minor、契約に影響しない修正は patch とする。
