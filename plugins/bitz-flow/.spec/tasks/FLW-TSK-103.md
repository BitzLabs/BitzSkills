---
implements: FLW-NFR-011
depends_on: []
boundary: scripts/agy_guard.py,tests/test_agy_guard.py,plugins/bitz-flow/.spec/tasks/FLW-TSK-103.md
status: implementing
---

### ガード資産へ出力できる Git option を fail-closed にする

- **作業内容**: `git show` / `git diff` / `git log` を読み取り専用として許可する際、
  `--output=<path>` のようにガード資産を書き換えられる option を通さない。`--` による
  pathspec は維持し、Git の option を含む形は既定 deny とする。
- **完了条件**: `--output` を用いて `agy_guard.py`、`hooks.json`、`settings.json` を指定する
  3種の陽性対照が deny され、既存の `git show HEAD:<path>` と `git log -- <path>` は通る。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
