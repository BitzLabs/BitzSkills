---
id: SDD-FR-124
version: 1.0
status: verified
domain: verification
priority: medium
origin: SI-SDD-009
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-124 unit-test 検証手段の統制語彙追加

- **対応設計**: SDD-DSN-001
- **説明**: `verification_method` の統制語彙へ `unit-test` を追加し、自動ユニットテスト・
  回帰テストによる検証を `example-test` と区別して記録できるようにする。
  語彙の正は引き続き spec_inspect.py の単一定義とし、spec_scaffold.py はそれを共有する。
  既存の `example-test` 要件は有効なまま維持し、遡及変更しない。
- **受入基準 (EARS)**:
  - WHEN spec_scaffold.py に `--verification-method unit-test` を指定する THEN システムは要件雛形を生成すること SHALL
  - WHEN active な要件が `verification_method: unit-test` を宣言する THEN spec_inspect.py は語彙外エラーを報告しないこと SHALL
  - WHERE spec_scaffold.py が検証手段を検査する THE システムは spec_inspect.py の統制語彙定義を共有すること SHALL
  - WHERE 既存要件が `verification_method: example-test` を宣言する THE システムはその要件を引き続き有効として扱うこと SHALL
  - WHEN `unit-test` を統制語彙として提供する THEN sdd-core は lifecycle.md と verification.md に自動ユニット／回帰テストを表す値であることを明記すること SHALL
  - WHEN 本要件を実装した変更をリリースする THEN 開発者は関連するスクリプト・規律文書・テスト・3マニフェストを同一プラグインリリースに含めること SHALL
  - WHEN 本要件を実装した変更を検収する THEN 開発者は release_check・全 pytest・全ワークスペースの spec inspect が PASS することを確認 SHALL
- **検証手段**: tests/test_spec_scaffold.py で scaffold の受理と単一定義共有を、
  tests/test_spec_inspect.py で active 要件の受理を自動検証する。lifecycle.md と verification.md の
  定義を目視確認し、全 pytest、release_check、全ワークスペースの spec inspect を実行する（example-test）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
  - 1.0 (2026-07-18) SI-SDD-009 の起票時前提を再検証。統制語彙は spec_inspect.py の
    VMETHODS が単一の正であり `unit-test` は未登録、scaffold は同定義を共有済みのため提案趣旨に乖離なし。
