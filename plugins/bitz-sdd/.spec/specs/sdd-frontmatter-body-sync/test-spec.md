# テスト仕様書: frontmatter境界を保持する本文双方向同期

sdd-test工程で SDD-FR-135 のEARS要件から導出したunit-test検証仕様。

- 実行日: 2026-07-19
- 対象リビジョン: base HEAD `f2b7db6` + working tree
- 検証ステータス: 検証済み
- **red記録**: `.venv/bin/pytest -q tests/test_sdd_sync.py` は
  **18 failed / 6 passed / exit 1**。raw copyによるfrontmatter流入、異常入力の無拒否、
  strict 5 ERROR、既存frontmatter非保持を確認した。

## テスト仕様: SDD-FR-135 frontmatter境界を保持する本文双方向同期

- **対象要件**: SDD-FR-135
- **導出元種別**: Event-Driven + Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_SDD_FR_135_pull_missing_target_uses_template_frontmatter_and_master_type`
  - `test_SDD_FR_135_pull_preserves_docs_frontmatter_and_syncs_only_spec_body`
  - `test_SDD_FR_135_pull_existing_doc_without_frontmatter_uses_template`
  - `test_SDD_FR_135_pull_rejects_source_without_frontmatter_without_modifying_docs`
  - `test_SDD_FR_135_pull_rejects_unclosed_docs_frontmatter_without_modification`
  - `test_SDD_FR_135_pull_rejects_invalid_master_type_before_generating_target`
  - `test_SDD_FR_135_pull_then_docs_inspect_strict_passes`
  - `test_SDD_FR_135_push_preserves_spec_frontmatter_and_syncs_only_docs_body`
  - `test_SDD_FR_135_push_rejects_docs_source_without_frontmatter`
  - `test_SDD_FR_135_push_rejects_missing_spec_target`
  - `test_SDD_FR_135_push_rejects_invalid_spec_target_without_modification`（2ケース）
- **既存契約の回帰**:
  - SDD-FR-100: 新しい側だけを同期し、同期後mtimeを同値化する
  - SDD-FR-126 / 128: 日本語6章の既存マッピングを維持する
  - SDD-FR-127: ドメインストーリー集約を維持する
- **green基準**: 対象テストの失敗・未許容skipが0件、全pytestがgreen、
  canonical spec inspectとrelease_checkがPASSすること。

## 検証結果

- 対象テスト: `.venv/bin/pytest -q tests/test_sdd_sync.py` → **24 passed**
- 全体テスト: `.venv/bin/pytest -q tests/` → **263 passed**
- docs strict: pull後の回帰テストで **0 findings**
- skill-validator: sdd-docsの構造、frontmatter、参照整合、本文品質を **全項目PASS**
- ローカル仕様検査: リポジトリ同梱 `spec_inspect.py --check-only` → **7/7 workspaces PASS**
- canonical仕様検査: `python3 scripts/spec inspect --workspace . plugins/*` → **7/7 workspaces PASS**
- リリース検査: `python3 scripts/release_check.py` → **PASS（全チェック合格）**
- バージョン: sdd-docs **1.1.0**、bitz-sdd **2.5.0**
