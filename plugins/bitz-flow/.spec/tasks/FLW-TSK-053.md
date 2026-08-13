---
implements: FLW-CON-002
depends_on: []
boundary: tests/test_m2_spec_consistency.py, plugins/bitz-flow/.spec/consistency-exceptions.json
status: done
---

### SI-FLW-052第1群のbitz-flow固有整合検査を実装する

- **作業内容**: `SI-FLW-052` の第1群から、文書改訂前に独立して固定できる構造検査を実装する。
  fixture catalog を SSOT とする M2-FLT 範囲、quarantine 区分数、Recovery ID の定義と参照を
  検査する。現存する既知乖離は件数付き例外リストへ固定し、新規追加・自然減・内容変化を
  いずれも CI で検出する。operation catalog、budget、汎用GP受領検査は関心事を分けた後続PRとする。
- **完了条件**: 各検査が正常系と不整合fixtureを持ち、現行の既知乖離だけを許容して
  `python3 <リポジトリ>/scripts/release_check.py`、全 pytest、canonical spec inspect が PASS すること。
  既知乖離を1件修正した際、例外を残したままでは stale exception として FAIL すること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
