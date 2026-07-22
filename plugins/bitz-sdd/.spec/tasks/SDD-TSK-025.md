---
implements: SDD-FR-141, SDD-FR-142
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py の collect() / _accepted_issue_ids / _origin_texts / next_actions
status: done
---

### spec_status.py の accepted 3値分類と実施記録欠落検出

- **作業内容**: SDD-DSN-004 の設計判断1・2を実装する。
  1. `_origin_texts()` を「(origin テキスト, 参照元要件 status) のペア」を返す内部ヘルパへ変更（非公開）。
  2. `collect()` の accepted spec-issue 判定を3分類化: ①対応済み（`**実施**:` マーカー or スコープ内 origin 参照）→ 非表示、②`delegated_to:` あり かつ ①非該当 → `accepted_delegated_unresolved` に計上、③それ以外 → 従来どおり `accepted_unaddressed`。
  3. `completion_record_missing` を算出: origin 参照で対応済み判定だが参照元要件 status が verified/promoted かつ本文に `**実施**:` マーカー無しのものを計上。
  4. JSON 出力に `accepted_delegated_unresolved` / `completion_record_missing` を加算（既存フィールドのキー・型は不変）。
  5. `next_actions` とテキスト出力に両フィールドの件数・対応候補文言を追加（委譲済みは「一括実行で判定 or 委譲先の要件化確認」、記録欠落は「対象issueに `**実施**:` を追記」＋参照要件ID/status）。
- **備考**: 読み取り専用を厳守（`.spec/` へ書き込まない）。`delegated_to:` の値解析はフィールド有無判定に留め、委譲先ファイル実在検証はしない（spec_inspect の管轄）。本文にタスク自身の ID を書かない（SI-CORE-002）。
