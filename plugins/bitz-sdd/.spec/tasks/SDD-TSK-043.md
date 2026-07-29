---
implements: SDD-FR-154
depends_on: [SDD-TSK-041]
boundary: skills/sdd-report/scripts/sdd_report.py, tests/test_sdd_report.py
status: done
---

### 統合レポートへ検証証跡を集計する

- **作業内容**: `sdd_report.py` に検証証跡の節を追加し、証跡ごとの commit・終了コード・
  対象要件を表へ出す。証跡が覆う要件数と失敗・不正な証跡の件数を集計し、失敗があれば
  総合ヘルスを RED にする。証跡ディレクトリが無いワークスペースでは節を出さない。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
