---
implements: SDD-FR-141, SDD-FR-142
depends_on: [SDD-TSK-025, SDD-TSK-026]
boundary: ルート SI-CORE-016/017/003 のデータ後付け、lifecycle.md 補強、sdd-core スキル + bitz-sdd プラグインの version bump
status: done
---

### データ衛生・規律文書・version bump

- **作業内容**: SDD-DSN-004 設計判断3 のデータ衛生と付随更新を行う。
  1. ルート `.spec/spec-issues/` の3件に後付け（確立済み書式）:
     - SI-CORE-016: frontmatter に `delegated_to: bitz-sdd:SDD-FR-120`、本文に `- **実施**:`（PR #45・SDD-FR-120 verified）
     - SI-CORE-017: frontmatter に `delegated_to: bitz-sdd:SDD-FR-121`、本文に `- **実施**:`（PR #45・SDD-FR-121 verified）
     - SI-CORE-003: frontmatter に `delegated_to: bitz-sdd:SDD-FR-001`、本文に `- **実施**:`（SDD-FR-001 reverse-derived・verified）
  2. `skills/sdd-core/references/lifecycle.md` に、委譲済み accepted の判定（単一/一括スコープの差）と
     実施記録欠落警告の節を補強する。
  3. `scripts/bump_version.py bitz-sdd minor` でプラグイン version を bump し、sdd-core スキル SKILL.md の
     `metadata.version` を semver minor bump・`updated` 更新。
  4. 後付け**前**に新警告2種（`accepted_delegated_unresolved` は単一スコープ、`completion_record_missing`）が
     実データで発火すること→後付け**後**に消えることを検証結果として記録する。
- **備考**: ルート `.spec` はリポジトリ内だが別ワークスペース。frontmatter + 本文追記のみでデータ移行なし。
  本文にタスク自身の ID を書かない（SI-CORE-002）。
