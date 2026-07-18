# テスト仕様書: 日本語6章docsレイアウトと安全な移行

sdd-test工程で SDD-FR-125、SDD-FR-126、SDD-FR-127、SDD-FR-128、SDD-FR-129 の
EARS要件から導出した検証仕様。

- 実行日: 2026-07-18
- 対象リビジョン: base HEAD `c6b133c` + working tree
- 実行コマンド: `.venv/bin/python -m pytest -q` / テンプレート `docs_inspect.py --strict` /
  `python3 scripts/release_check.py` / `python3 scripts/spec inspect --workspace . plugins/*`
- 結果: 全pytest **220 passed in 3.66s** / テンプレートstrict **ERROR 0 / WARN 0 / INFO 0** /
  release_check **PASS**

## テスト仕様: SDD-FR-125 日本語6章文書構成と宣言式拡張

- **対象要件**: SDD-FR-125
- **導出元種別**: Event-Driven + State-Driven + Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_japanese_six_chapter_template_passes_strict`
  - `test_missing_mandatory_chapter_is_error`
  - `test_legacy_chapter_mixed_with_japanese_layout_is_error`
  - `test_optional_reference_requires_master_declaration`
  - `test_declared_optional_reference_passes`
  - `test_excluded_path_skips_unmanaged_research_docs`
  - `test_excluded_path_cannot_hide_managed_chapter`
- **結果**: 7件green。実テンプレートのstrict検査もfinding 0件。

## テスト仕様: SDD-FR-126〜128 日本語章への双方向同期

- **対象要件**: SDD-FR-126 / SDD-FR-127 / SDD-FR-128
- **導出元種別**: Event-Driven + State-Driven
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_pull_new_file` / `test_pull_docs_newer_no_overwrite` / `test_pull_spec_newer_overwrites`
  - `test_pull_stories_aggregation`
  - `test_push_docs_newer_reverses_sync` / `test_push_spec_newer_no_reverse_sync`
  - `test_pull_uses_japanese_mapping`（6マッピング）
  - `test_push_design_doc_uses_japanese_mapping`
  - `test_diff_is_readonly` / `test_pull_does_not_modify_unrelated_docs`
- **結果**: 15件green。Discoveryの未実装マッピングはSI-SDD-011へ分離したまま維持。

## テスト仕様: SDD-FR-129 旧8章から日本語6章への安全な移行

- **対象要件**: SDD-FR-129
- **導出元種別**: Event-Driven + Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_default_is_readonly_dry_run`
  - `test_apply_migrates_and_strict_inspection_passes`
  - `test_conflict_stops_before_any_change`
  - `test_rollback_restores_legacy_tree`
  - `test_second_apply_is_idempotent`
  - `test_reference_migration_declares_optional_chapter`
- **結果**: 6件green。apply前の一括衝突検査、hash付きmanifest、全hash事前照合rollbackを確認。

## Design Review / Skill Validation

- SDD-REV-002: consistency 4.70 / operations 4.50 / risk 4.67 / business 4.60、
  正規化総合4.62、critical 0 / major 0、統合判定 **PASS**。
- skill-validator: 変更対象8スキルについて frontmatter、発動条件、500行以内、参照先、
  実行安全性をチェックし、全項目 **PASS**。プラグイン間参照は対象スキル名を明記した
  連携ポインタであり、相対参照による依存ではないことを確認。

- **検証ステータス**: **verified** — canonical spec inspection は全7ワークスペースで
  問題0・幽霊参照0・孤児要件0・判定PASS。
