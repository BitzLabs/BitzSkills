### テスト仕様: FLW-NFR-009 M0評価の全採点proxy台帳と乖離防止

- **対象要件**: FLW-NFR-009
- **EARS 節**: proxy変更、compact envelope採点、曖昧候補、全量・省略出力、採点規則変更の各WHEN節
- **導出元種別**: Event-Driven
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_FLW_NFR_009_proxy_registry_matches_design_ledger`
  - `test_FLW_NFR_009_allows_preamble_before_compact_envelope`
  - `test_FLW_NFR_009_rejects_wrong_operation_and_ambiguous_envelopes`
  - `test_FLW_NFR_009_rejects_non_envelope_output`
  - `test_FLW_NFR_009_accepts_consistent_compact_truncation`
  - `test_FLW_NFR_009_rejects_inconsistent_compact_truncation`
  - `test_FLW_NFR_009_rejects_missing_item_without_truncation`
  - `test_FLW_NFR_009_scoring_rule_tracks_all_inputs`
  - `test_FLW_NFR_009_manifest_keeps_judgment_history`
  - `test_FLW_NFR_009_manifest_replaces_same_result_identity`
  - `test_FLW_NFR_009_missing_raw_log_rescore_is_unknown`
- **検証ステータス**: `spec_verify.py record` が生成する `.spec/verification/` の機械可読証跡を正とする。
- **再採点監査**: `evals/flow-core/m0-eval/rescoring-2026-08-11-flw-nfr-009.json`。保存済みraw logが全件参照切れのため説明済み2差分も`unknown`とし、Gate切替をblockedに保った。
