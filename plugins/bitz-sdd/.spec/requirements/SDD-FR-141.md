---
id: SDD-FR-141
version: 1.0
status: verified
domain: reporting
priority: medium
origin: SI-SDD-025
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-141 spec_status の委譲済み accepted spec-issue を未着手から分離集計する

- **説明**: `spec_status.py`（CORE-FR-003 / CORE-FR-012）の `accepted_unaddressed` は、accepted な
  spec-issue の完了を「本文の `- **実施**:` マーカー」または「実行スコープ内のいずれかの
  workspace の要件 `origin:` 参照」でのみ判定する。ルートの spec-issue を `delegated_to:` で
  サブワークスペースへ委譲し、サブ側で要件化・実装した場合、実行スコープに委譲先 workspace が
  含まれない単一スコープ実行（例: `spec status .`）ではその origin 参照を辿れず、完了済みでも
  恒常的に「未着手の accepted」と誤報告する。本要件は、`delegated_to:` を持つが対応済み判定に
  該当しない accepted spec-issue を、`accepted_unaddressed` とは別の新規フィールド
  `accepted_delegated_unresolved` へ分離集計し、単一スコープ実行時の false-positive を除去する
  （読み取り専用のまま。既存フィールドのキー・型は変更しない）。
- **受入基準 (EARS)**:
  - WHEN accepted spec-issue が frontmatter に `delegated_to:` を持ち、かつ実行スコープ内の
    いずれの workspace の要件 `origin:` にもその ID への言及が無く、本文に `- **実施**:` マーカーも
    無い THEN その spec-issue を `accepted_unaddressed` に含めず `accepted_delegated_unresolved` に
    計上すること SHALL
  - WHEN accepted spec-issue が `delegated_to:` を持ち、かつ実行スコープ内の要件 `origin:` 参照
    または `- **実施**:` マーカーで対応済みと判定される THEN `accepted_delegated_unresolved` にも
    `accepted_unaddressed` にも含めないこと SHALL
  - WHEN accepted spec-issue が `delegated_to:` を持たず origin 参照も実施マーカーも無い
    THEN 従来どおり `accepted_unaddressed` に計上し `accepted_delegated_unresolved` には含めない
    こと SHALL
  - WHEN `accepted_delegated_unresolved` が1件以上存在する THEN 人間向けテキスト出力・
    `next_actions` 双方に、件数と「委譲先 workspace を含む `--workspace` 一括実行で判定するか
    委譲先の要件化状況を確認する」旨の対応候補を含めること SHALL
  - WHEN `--json` を指定して実行する THEN JSON 出力に `accepted_delegated_unresolved`（ID 一覧）を
    含む新規フィールドを追加すること SHALL
  - THEN 本機能の追加によって `accepted_unaddressed` を含む既存 JSON フィールドのキー・型・
    出力可否は変更されないこと SHALL（`accepted_unaddressed` から委譲済み分が除外される点を除き非破壊的）
  - THEN 本機能も `.spec/` 配下への書き込みを一切行わないこと SHALL（読み取り専用）
- **検証手段**: `tests/test_spec_status.py` に fixture（`delegated_to` 持ち・origin 参照なしの
  accepted spec-issue、単一スコープと一括スコープ双方）を追加し、`accepted_delegated_unresolved`
  への計上・`accepted_unaddressed` からの除外・JSON フィールド・テキスト/next_actions 文言を
  検証する。加えて本リポジトリのルート workspace 単一実行で SI-CORE-016/017/003 が
  `accepted_unaddressed` から消える（データ後付け後）ことを確認する（example-test）。
- **Revision History**:
  - 1.0 (2026-07-22) 初版（draft 起票）。origin: SI-SDD-025。設計は SDD-DSN-004
