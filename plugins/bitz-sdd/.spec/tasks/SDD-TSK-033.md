---
implements: SDD-FR-145
depends_on: [SDD-TSK-032]
boundary: skills/sdd-core/scripts/spec_inspect.py, spec_status.py, skills/sdd-report/scripts/sdd_report.py, tests/test_spec_inspect.py
status: pending
---

### schema v2 検査と経路別集計（inspect・status・report）

- **作業内容**: `spec_inspect.py` の監査検査を schema_version 1 / 2 の併存受理へ拡張し、
  provenance kind 別の必須フィールド検査（proxy は `on_behalf_of` / `decision_ref` 必須）と、
  パス形式 decision_ref の参照先消失 WARN を実装する。`spec_status.py` と `sdd_report.py` に
  人間裁定必須遷移の経路別（対話確認 / 代行）分離集計を追加し、unit-test を先行追加する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
