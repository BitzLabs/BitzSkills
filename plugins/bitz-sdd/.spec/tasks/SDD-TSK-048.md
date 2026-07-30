---
implements: SDD-FR-159
depends_on: [SDD-TSK-047]
boundary: skills/sdd-core/scripts/spec_inspect.py, tests/test_spec_inspect.py
status: done
---

### 未紐づけの P0/P1 と tracked_by の実在を spec_inspect で検査する

- **作業内容**: `spec_inspect.py` に未紐づけ P0/P1 の検出を追加し、該当があれば finding ID を
  列挙して非ゼロ終了させる。`verdict: PASS` との併存は追加の不整合として報告する。
  `tracked_by` は spec-issue ID なら全ワークスペース横断の既知 ID 集合で、
  `<REV-ID>:GP-NNN` 形式なら同一レビューの `gate_preconditions` で実在検査する。
  **検査は `spec_inspect` に置き**、レポート生成（`sdd_report`）の実行有無に依存させない —
  判定は Core が持ち、可視化コンテキストは読み取り専用の読取モデルであるため。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
