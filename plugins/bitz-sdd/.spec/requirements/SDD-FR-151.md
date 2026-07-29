---
id: SDD-FR-151
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-SDD-016
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-151 検証コマンド実出力からの機械可読証跡の記録

- **説明**: 検証結果を人手で test-spec へ書き写す運用では、同じコミット・同じ結果の再実行でも
  実行時間の揺れによって文書値と最新値が食い違い、green 判定の再現性が人手に依存する。
  そのため検証コマンドを実行して実出力から証跡を生成する記録手段を設け、green 判定に必要な
  安定情報（commit・終了コード・件数・tool version）と観測値（実行時間）を分離する。
  証跡は実行単位で 1 ファイルとし、同一 commit・同一 command-id の再実行は同じファイルを
  上書きして冪等にする。実行時間は `observed` に隔離し、一致判定には用いない。
  本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `spec_verify.py record` が検証コマンドとともに実行されたとき THEN システムは当該コマンドを実行し、その終了コードを証跡へ記録する SHALL
  - WHEN 証跡を書き出すとき THEN システムは schema 識別子・command_id・コマンド引数・40桁の commit SHA・UTC 実行時刻・tool 名と version・終了コード・対象要件 ID を安定項目として記録する SHALL
  - WHEN 証跡を書き出すとき THEN システムは実行時間を `observed` 配下へ分離し、安定項目に含めない SHALL
  - WHEN 同一 commit・同一 command_id で再実行されたとき THEN システムは同じ経路のファイルへ上書きし、証跡ファイルを増やさない SHALL
  - WHEN 検証コマンドの出力が pytest の要約形式であるとき THEN システムは passed / failed / errors / skipped の件数を証跡へ記録する SHALL
  - IF 作業ツリーに未コミットの変更があり `--allow-dirty` が指定されていない THEN システムは証跡を書き出さず非ゼロ終了する SHALL
  - IF git の HEAD を解決できない THEN システムは証跡を書き出さず非ゼロ終了する SHALL
  - IF 指定された要件 ID の書式が不正である THEN システムはコマンドを実行せず非ゼロ終了する SHALL
- **検証手段**: `tests/test_spec_verify.py` の unit-test（記録の成否・安定項目と observed の分離・
  冪等な上書き・pytest 件数の解析・dirty 拒否と `--allow-dirty` 許可・HEAD 未解決時の拒否・
  要件 ID 書式の拒否）。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-016 から導出。
