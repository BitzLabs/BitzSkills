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
- **是正後の再実測**: 第14ラウンドでは3 platform × 123件を新規実測し、必須field保持は
  189/189、Cross-model Decision Parityは100%となった。統合証跡は
  `evals/flow-core/m0-eval/run-manifest-3platform-2026-08-11-r14.json`。全369件のraw log
  digestを解決でき、正規採点器は終了コード0でPASSした。人間裁定により結果ID
  `84c6f45324f547723d6a63f40c352c5997b083503c2155e194256e0c584597e6`を`active`に選択した。
