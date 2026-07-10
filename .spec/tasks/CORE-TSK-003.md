---
id: CORE-TSK-003
implements: CORE-FR-002
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py, tests/test_spec_inspect.py
status: done
---

### CORE-TSK-003 scan_refs の自己言及除外と回帰テスト

- **作業内容**: scan_refs でファイル名 stem と一致する ID を参照から除外。
  tests/test_spec_inspect.py を新設（自己言及の非検出 / 真の幽霊参照の検出継続の2ケース）。
- **実施記録**: 2026-07-11 実施。sdd-core 1.7.1 / bitz-sdd を patch bump。
- **備考**: 本タスクは修正の実証として、本文とfrontmatter に自身の ID を明記している
  （修正前ならこの書き方は幽霊参照で FAIL していた）。
