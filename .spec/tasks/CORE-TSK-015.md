---
implements: CORE-CON-009
depends_on: []
boundary: plugins/plugin-creator/skills/plugin-structure/references/migration-steps.md, plugins/plugin-creator/skills/plugin-structure/references/lifecycle-skills.md, plugins/plugin-creator/skills/plugin-structure/SKILL.md, plugins/skill-creator/skills/skill-packager/references/lifecycle.md, マニフェスト6ファイル（plugin-creator/skill-creator の version bump）
status: done
---

### update マイグレーション機構の規約 reference を追加

- **作業内容**: DSN-002（approved）を正として、
  1. `plugins/plugin-creator/skills/plugin-structure/references/migration-steps.md` を新設し、
     マイグレーションステップの書式（from/to/targets/transform/guard/verify/rollback、
     1ファイル1ステップ `references/migrations/<from>-to-<to>.md`）、プラグイン version 軸と
     D の読み取り元、チェーン解決と安全側停止条件、実行順序（コミットマーカー方式）、
     リポジトリ外書き込みの承認フロー、doctor 連携（任意）、合成フィクスチャによる確認手順を規定する。
  2. `references/lifecycle-skills.md` の `update` 行と本文にマイグレーション機構（任意拡張）への
     言及と migration-steps.md への参照を追記する。
  3. plugin-structure の SKILL.md の追加リソース一覧に migration-steps.md を追記する。
  4. `plugins/skill-creator/skills/skill-packager/references/lifecycle.md` に責務境界
     （packager=置き換え可否判定、update マイグレーション=状態変換。二重規定回避）を追記する。
  5. plugin-creator を minor、skill-creator を patch で `scripts/bump_version.py` により bump する。
- **実施記録**: 2026-07-18 実施。migration-steps.md 新設・lifecycle-skills.md / SKILL.md /
  packager lifecycle.md 追記・plugin-creator 1.3.0（minor）/ skill-creator 0.5.3（patch）bump。
  release_check PASS・spec_inspect --workspace . plugins/* 全6ワークスペース PASS・pytest 159 green。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
