# テスト仕様書: spec_inspectの並列開発向け検査契約

sdd-test工程で SDD-FR-133 / SDD-FR-134 のEARS要件から導出した検証仕様。

- 実行日: 2026-07-19
- 対象リビジョン: base HEAD `88071d1` + working tree
- 最終実行コマンド: `.venv/bin/pytest -q tests/` /
  `python3 scripts/spec inspect --workspace . plugins/*` /
  `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py --workspace . plugins/* --check-only` /
  `python3 scripts/release_check.py`
- 最終結果: pytest **254 passed** / canonical spec inspect **全7ワークスペースPASS** /
  ローカル2.4.0 check-only **全7ワークスペースPASS・レポート差分ゼロ** /
  release_check **PASS**

## テスト仕様: SDD-FR-133 check-only読み取り専用検査

- **対象要件**: SDD-FR-133
- **導出元種別**: Event-Driven + State-Driven + Unwanted Behavior
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_SDD_FR_133_check_only_preserves_existing_report_and_matches_output`
  - `test_SDD_FR_133_check_only_does_not_create_missing_report`
  - `test_SDD_FR_133_check_only_failure_does_not_write_report`
  - `test_SDD_FR_133_check_only_preserves_all_workspace_reports`
- **red記録**: 実装前の3件はFAIL。`--check-only` が未定義のため終了コード2となった。
- **green記録**: 単一・複数workspaceを含む対象4件green。新規対象全7件green、
  最終全体実行は254 passed。

## テスト仕様: SDD-FR-134 approved実装待ちと孤児FAILの分離

- **対象要件**: SDD-FR-134
- **導出元種別**: Event-Driven + State-Driven
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_SDD_FR_134_approved_without_task_is_warning_and_passes`
  - `test_SDD_FR_134_post_approval_without_task_is_orphan_and_fails`
  - `test_SDD_FR_134_approved_with_task_is_not_waiting`
- **red記録**: 実装前は3件FAIL。approved未紐付けが孤児FAILとなり、実装待ち節も存在しなかった。
- **green記録**: 対象3件green。新規対象全7件green、最終全体実行は254 passed。

- **検証ステータス**: green
