---
id: CORE-FR-012
version: 1.2
status: verified
domain: tooling
priority: medium
origin: SI-CORE-025
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-012 spec_status.py による accepted 未着手 spec-issue の検知

- **説明**: `spec_status.py`（CORE-FR-003）の次アクション候補は、`status: accepted` の
  spec-issue のうち requirement へ分解されていないもの（＝積み残し）を検知できず、
  実際には未着手の作業があっても「クリーン」と報告してしまう。本要件は、accepted spec-issue の
  ID を各 workspace の `requirements/*.md` の `origin:` フィールドと突合し、参照が一件も無い
  ものを「未着手の accepted」として集計・提示する機能を CORE-FR-003 の出力に追加する
  （読み取り専用のまま。CORE-FR-003 の既存 EARS 節・既存出力フィールドは変更しない）。
- **受入基準 (EARS)**:
  - WHEN `status: accepted` の spec-issue があり、いずれの workspace の `requirements/*.md` の `origin:` にもその ID への言及が無い THEN その spec-issue を「未着手の accepted」として件数集計に含めること SHALL
  - WHEN `status: accepted` の spec-issue が frontmatter に `delegated_to:` を持ち、かつ実行スコープ内のいずれの workspace の `origin:` にもその ID への言及が無く、本文に `**実施**:` マーカーも無い THEN その spec-issue を「未着手の accepted」（`accepted_unaddressed`）には含めず、委譲済み・未解決として別フィールド（例: `accepted_delegated_unresolved`）に分離集計すること SHALL（上記節への例外。単一スコープ実行では委譲先 workspace の `origin:` を辿れず false-positive になるのを防ぐ。詳細契約は bitz-sdd の SDD-FR-141 が正）
  - WHEN `origin:` フィールドに spec-issue ID への言及がある THEN その spec-issue を「未着手の accepted」に含めないこと SHALL（部分一致でよい。表記ゆれは見逃し防止側に倒す）
  - WHEN spec-issue 本文に `**実施**:` で始まる行がある（軽量レーンで直接反映済みの完了マーカー） THEN `origin:` 参照の有無に関わらずその spec-issue を「未着手の accepted」に含めないこと SHALL
  - WHEN 「未着手の accepted」が1件以上存在する THEN 人間向けテキスト出力・`next_actions` 双方にその件数と対応候補（要件化 or 軽量レーンでの実施の検討を促す文言）を含めること SHALL
  - WHEN `--json` を指定して実行する THEN JSON 出力に「未着手の accepted」spec-issue の ID 一覧を含む新規フィールド（例: `accepted_unaddressed`）を含めること SHALL
  - THEN 本機能の追加によって CORE-FR-003 の既存 EARS 節（status 別件数集計・JSON/テキスト出力・読み取り専用・複数 workspace 対応）の受入基準は一切変更されないこと SHALL
  - THEN 本機能も `.spec/` 配下への書き込みを一切行わないこと SHALL（読み取り専用）
- **検証手段**: `tests/test_spec_status.py` に fixture（accepted だが `origin:` 未参照の
  spec-issue を含む `.spec` ツリー）を追加し、集計・JSON フィールド・テキスト出力を検証する。
  加えて本リポジトリのルート workspace で実行し、SI-CORE-007/008/009/010/013/014/018 が
  「未着手の accepted」として実地検出されることを確認する（example-test）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
  - 1.1 (2026-07-18) 実装着手前に判明した誤検知（bitz-env の軽量レーン完了7件が毎回
    「未着手」と誤表示される）を防ぐため、`**実施**:` マーカーによる除外基準を追加
    （人間裁定「実施マーカーも対応済みとみなす」により承認。既存の3節は変更なし=非破壊的追加）
  - 1.2 (2026-07-22) クロスワークスペース委譲済み spec-issue が単一スコープ実行で恒常的に
    「未着手」と誤報告される欠陥（SI-SDD-025）に対し、`delegated_to:` を持つものを
    `accepted_unaddressed` から分離集計する例外節を追加（既存節への非破壊的な例外追加。
    実装契約は bitz-sdd SDD-FR-141。co-design は SDD-DSN-004。人間裁定により承認）
