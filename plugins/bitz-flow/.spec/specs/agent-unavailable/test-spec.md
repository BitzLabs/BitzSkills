### テスト仕様: FLW-NFR-010 platform固有の測定不能署名

- **対象要件**: FLW-NFR-010
- **EARS 節**: platform固有拒否、実行痕跡、raw log永続化の各WHEN節
- **導出元種別**: Event-Driven
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_FLW_NFR_010_claude_rejected_event_is_unavailable_despite_success_subtype`
  - `test_FLW_NFR_010_claude_text_without_error_or_rejection_is_not_unavailable`
  - `test_FLW_NFR_010_platform_specific_unavailable_signals`
  - `test_FLW_NFR_010_raw_log_is_defaulted_and_resolvable`
  - `test_FLW_NFR_010_quota_error_with_execution_traces_is_a_real_failure`
- **検証ステータス**: `.spec/verification/`の機械可読証跡を正とする。
- **是正後の再実測**: 第14ラウンドの有効な3 platform × 123件では測定不能0件、
  `runner_exit_code=0`、raw log参照解決369/369を確認した。antigravity初回`r14`は
  サンドボックスのホーム書込み制限で全件終了コード1となったため環境エラー証跡として除外し、
  制限を解消した`r14b`を採点対象とした。
