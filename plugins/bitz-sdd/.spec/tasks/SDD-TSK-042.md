---
implements: SDD-FR-153
depends_on: [SDD-TSK-041]
boundary: skills/sdd-core/scripts/spec_inspect.py, skills/sdd-core/references/verification.md, tests/test_spec_inspect.py
status: done
---

### 検証証跡を spec_inspect で検査する

- **作業内容**: `.spec/verification/` を読み、schema 不正・必須キー欠落・非ゼロ終了・
  failed 件数・参照切れを FAIL、HEAD と異なる commit・dirty 記録・証跡欠落を WARN として
  検査レポートへ出す。証跡ディレクトリを持たないワークスペースは従来どおり無検査とし、
  加法的導入を保つ。`manual-check` の要件は証跡欠落 WARN の対象から外す。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
