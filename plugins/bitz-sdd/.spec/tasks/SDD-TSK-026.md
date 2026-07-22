---
implements: SDD-FR-141, SDD-FR-142
depends_on: [SDD-TSK-025]
boundary: tests/test_spec_status.py の fixture 追加（make_spec 拡張含む）
status: done
---

### test_spec_status.py に委譲判定・記録欠落の回帰 fixture を追加

- **作業内容**: SDD-DSN-004 設計判断5 のテスト先行契約を固定する。`make_spec` ヘルパに
  `issue_delegated_to`（spec-issue frontmatter に `delegated_to:` を差し込む）と要件 status を
  origin と紐づける拡張を加え、以下10ケースを追加する（テスト名に SDD-FR-141 / SDD-FR-142 を含める）:
  1. accepted + `**実施**:` マーカー → どのフィールドにも計上しない（既存回帰の確認）
  2. accepted + 同一WS origin 参照 → unaddressed に計上しない（既存回帰）
  3. accepted + クロスWS origin 参照（一括実行）→ unaddressed に計上しない
  4. accepted + `delegated_to` あり・スコープ内 origin 参照なし（単一実行）→ `accepted_delegated_unresolved` に計上・unaddressed に含めない
  5. 同上・一括実行でも origin 参照なし → 同上＋next_actions 文言を含む
  6. origin 参照あり・要件 verified・マーカーなし → `completion_record_missing` に計上
  7. origin 参照あり・要件 draft/approved/implementing・マーカーなし → 警告しない
  8. origin 参照あり・要件 verified・マーカーあり → 警告しない
  9. open / deprecated / superseded の spec-issue → いずれの新フィールドにも計上しない
  10. JSON 既存フィールド（`accepted_unaddressed` ほか）のキー・型が不変（公開契約の回帰）
- **備考**: fixture ID は連結で組み立てる既存流儀を踏襲（本ファイルが幽霊参照検出されないように）。
  本文にタスク自身の ID を書かない（SI-CORE-002）。
