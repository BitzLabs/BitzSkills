---
implements: SDD-FR-123, SDD-FR-124
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/**, plugins/bitz-sdd/skills/sdd-test/**, tests/test_spec_scaffold.py, tests/test_spec_inspect.py, plugins/bitz-sdd/.claude-plugin/plugin.json, plugins/bitz-sdd/plugin.json, plugins/bitz-sdd/.codex-plugin/plugin.json
status: done
---

### 検証証跡基準と unit-test 語彙を実装

- **作業内容**: 軽量レーンの検証証跡について、STATE.md を正本とする必須フィールド、
  green 条件、スキップ統制、PR の有無と秘匿情報除去、非遡及を lifecycle と sdd-test に明記する。
  あわせて spec_inspect.py の統制語彙へ `unit-test` を追加し、scaffold が共有定義から受理することを
  回帰テストで固定する。sdd-core / sdd-test の metadata と bitz-sdd の3マニフェストを patch bump する。
- **実施方針**: 両要件は文書・プラグイン version の境界が重なるため1タスクで原子的に実装する。
  共有スクリプト変更を含むため、対象テストだけでなく全 pytest を検収で実行する。
- **実施記録**: 2026-07-18 実施。対象テスト red 2件 → green 2件、Design Review PASS、
  skill-validator A〜F PASS、release_check PASS、pytest 167件 green、
  spec inspect 全7ワークスペース PASS。bitz-sdd 1.11.4へ patch bump。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
