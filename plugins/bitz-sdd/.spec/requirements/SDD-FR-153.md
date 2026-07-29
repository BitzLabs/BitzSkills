---
id: SDD-FR-153
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

### SDD-FR-153 検証証跡の構造検証と参照切れ検出

- **説明**: 証跡は生成しただけでは信用できない。壊れた証跡・失敗した実行の証跡・存在しない
  要件を指す証跡が放置されると、機械可読化そのものが偽の安心を与える。`spec_inspect.py` は
  証跡を読み、明確な異常（schema 不正・必須キー欠落・非ゼロ終了・失敗件数・参照切れ）を
  FAIL とする。一方、証跡は加法的に導入するため、証跡が無いこと自体と、HEAD と異なる
  commit の証跡は WARN に留めて既存ワークスペースの判定を壊さない。
  `.spec/verification/` を持たないワークスペースは従来どおり無検査とする。
  本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - IF ワークスペースに `.spec/verification/` が存在しない THEN システムは証跡検証を行わず、従来と同一の判定を出す SHALL
  - IF 証跡が JSON として読み取れない、または schema 識別子が想定と異なる THEN システムは問題として報告し FAIL する SHALL
  - IF 証跡に必須キーが欠落している THEN システムは欠落キーを示して FAIL する SHALL
  - IF 証跡の終了コードが 0 でない THEN システムは失敗した実行の証跡として FAIL する SHALL
  - IF 証跡の件数に failed または errors が 1 以上ある THEN システムは FAIL する SHALL
  - IF 証跡が登録簿に存在しない要件 ID を指している THEN システムは参照切れとして FAIL する SHALL
  - IF 証跡の記録時 commit 以降に証跡ディレクトリ以外のファイルが変更されている THEN システムは古い証跡として WARN を報告し、FAIL にしない SHALL
  - WHEN 証跡の記録時 commit 以降の変更が証跡ディレクトリ配下だけであるとき THEN システムは当該証跡を古いと見なさない SHALL
  - IF 要件が verified または promoted であり `manual-check` 以外の検証手段を持つのに証跡が無い THEN システムは WARN を報告し、FAIL にしない SHALL
  - WHEN 証跡が 1 件以上あるとき THEN システムは検査レポートへ証跡の一覧と WARN の節を出力する SHALL
- **検証手段**: `tests/test_spec_inspect.py` の SDD-FR-153 unit-test（証跡ディレクトリ不在時の
  無変化、schema 不正・必須キー欠落・非ゼロ終了・failed 件数・参照切れの各 FAIL、
  証跡以降のソース変更による WARN 化と証跡のみの変更を古いと見なさないこと、証跡欠落の WARN 化、レポート節の出力）。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-016 から導出。
