---
implements: CORE-FR-013
depends_on: []
boundary: tests/test_release_check.py, scripts/release_check.py, plugins/plugin-creator/skills/plugin-structure/**, plugins/plugin-creator/**/plugin.json
status: implementing
---

### release_check への依存グラフ検証の追加（テスト先行）

- **作業内容**:
  1. **テスト先行**: `tests/test_release_check.py` に依存検証の回帰テストを追加する
     （依存先不在 FAIL / 循環 FAIL / semver 制約不満足 FAIL / 3マニフェスト不一致 FAIL /
     依存宣言なし PASS）。先にテストのみコミットして red を確認する
  2. `scripts/release_check.py` に `metadata.dependencies` の依存グラフ検証を追加して green にする
  3. `metadata.dependencies` の書式を plugin-structure の references に、
     init / doctor / update 時の依存確認手順を lifecycle-skills.md（CORE-CON-008）に追記する
  4. plugin-creator の version bump（依存宣言書式という新規記載の追加のため minor）
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
