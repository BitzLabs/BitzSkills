---
id: SDD-FR-154
version: 1.0
status: verified
domain: reporting
priority: medium
origin: SI-SDD-016
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-154 統合レポートへの検証証跡集計

- **説明**: 人間が読む統合レポートに証跡が現れなければ、機械可読化しても検証状況の把握は
  test-spec の手書き値に戻ってしまう。`sdd_report.py` は `.spec/verification/` を集計し、
  証跡ごとの commit・終了コード・対象要件と、証跡が覆う要件数・失敗件数をレポートへ含める。
  失敗した証跡がある場合は総合ヘルスへ反映する。証跡ディレクトリを持たないワークスペースでは
  当該節を出力せず、既存レポートの構成を変えない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - IF ワークスペースに `.spec/verification/` が存在しない THEN システムは検証証跡の節をレポートへ出力しない SHALL
  - WHEN `.spec/verification/` が存在するとき THEN システムは証跡ごとにファイル名・commit・終了コード・対象要件をレポートの表へ出力する SHALL
  - WHEN 検証証跡を集計するとき THEN システムは証跡が覆う要件数と失敗・不正な証跡の件数をレポートへ出力する SHALL
  - IF 終了コードが 0 でない証跡または読み取れない証跡が 1 件以上ある THEN システムは総合ヘルスを RED として報告する SHALL
- **検証手段**: `tests/test_sdd_report.py` の SDD-FR-154 unit-test（証跡不在時に節が出ないこと、
  証跡ありのときの表の内容、覆う要件数と失敗件数、失敗証跡による総合ヘルス RED 化）。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-016 から導出。
