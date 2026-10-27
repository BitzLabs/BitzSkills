# Phase 4：JSON型を区別する証拠照合の是正（2026-10-08）

型を保つJSON照合へ修正し、確定source `dad596b2034bbcd0abb4cd25c19aea78143aa5a3` の
全426件と原証拠再照合は通過した。修正版の独立再検分は新payloadの明示承認待ちである。
Phase/Step/Gate完了、指摘解消済み、実provider・一次評価・期待行動は認定しない。

## 実施した独立検分と再現

ユーザーの明示承認後、source `f62a87a6181831f87cd24de72c843588869dd736` の5ファイルを
OpenAI Codex CLI `gpt-6.1-sol` へ送る独立静的検分1回を実行した。
原保存先は `.venv/sdk-trace-independent-review-05`、CLI exit0、timeoutなし、receiptはreview_findings。
P2=1/P3=1、一次0、委譲0、自動retry0。この有限枠は消費1/残0。
前回の送信拒否と承認待ち報告は、commit `a29eb28296a4ae8c0293c98178e5fc2b93a9bc63` 時点の履歴として保持する。

- P2：host/native/providerのJSON結果に、数値と真偽値を等しいとするPython比較が残っていた。
- P3：SDKのexperimentalApiとsandbox.networkAccessでも1/0への型置換を通した。

親は同sourceで次の実出力を得た：

```text
integer-capability: sdk_child_trace_diagnostic_passed
integer-network: sdk_child_trace_diagnostic_passed
boolean-native-result: sdk_child_trace_diagnostic_passed
```

最後の条件は合成manifestのcandidateVersionを数値1とし、native結果の同字段だけtrueへ改変した入力である。
固定71資源のsnapshotを改変した実測とは扱わない。
親は原stdout/応答/schema/usage/全source hash/Git bytes/前後guardを再照合した。
実出力はreview05_terminal_schema_and_findings_rechecked/P2=1/P3=1/exitCode=0。
検分者自身の試験実行や全原実行証拠の検証とは扱わない。

- 原review receipt SHA256：`0f8fd777c401e66d246babea04bb81ae0465913fa5aa4b260d975e7c3621e326`
- 原review応答 SHA256：`baabaaa31ddafbf45e34f9f38fe5430713fd3cb79f8bfdcfcb7035c14e80fd2e`
- 原usage：input31457/output2086/reasoning1552（reasoningはoutputの内訳として別記し、加算しない）。

## 修正と回帰試験

共通 `production_trace.json_equal` はJSON objectのキー順序を正規化し、bool/int/floatと配列順序を保つ。
host/native/providerの本文とstructuredContent、最終応答、入力/summary/prefix/設定/アイテム照合へ適用した。
experimentalApi=true、networkAccess=falseの辞書も型を区別する。
SSEのoutput/content indexと原telemetryのattempt/status codeは整数型を要求する。
questionsの未指定/null/空配列と0/false/空文字/空objectを区別し、SSE response IDは非空文字列に限定した。

対象87件は0.743s/OK/exit0。JSON objectのキー順序だけが違う正常な証拠は通す。
初期SSE回帰入力の余分な改行で1件が意図した拒否理由へ到達せず、87件/0.761s/exit1となった。
改行を修正し、indexとIDの試験では実際の拒否理由も確認する。旧実出力の成功へ訂正はしない。
途中source `48c4951500b2cf0653dfb36bb2697a711fe37a1d` の424件/62.833s/exit0も原保存先06に残す。

最終sourceの全件・原証拠再照合コマンド：

```sh
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py --source dad596b2034bbcd0abb4cd25c19aea78143aa5a3
```

実出力はsdk_parent_links_artifacts_rechecked/tests.count426/tests.seconds61.879/tests.exitCode0。
原テストstderr終端は `Ran 426 tests in 61.879s` / `OK`。
原hash/source/全71資源Git/対象原telemetry全19行/固定1execの親call・cell・2子IDを照合した。
前後source guard一致、clean treeで測定した。保存先は `.venv/production-sdk-parent-links-verification-07`。
テストstderr SHA256は `e8053c6d7f557dc2e8b9cbe65a0e6941a95d57a3157a6465ac0c2c9ad5b13934`。

公開要約を原保存物・歴史Git・未起動の送信候補へ再照合するコマンド：

```sh
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-08-sdk-json-type-remediation/verify-recorded-results.py
```

実出力はrecorded_results_match_original_bytes/tests426/originalReviewFindings(P2=1,P3=1)/
newIndependentReviews1/pendingReviewInvocations0/eligibleForMeasurement=false、exit0。
この再照合は外部通信・モデル起動・書込み・全試験の再実行を行わない。

今回の新mock/ローカルHTTP要求は0。過去のread-06を照合しており、新規試行へ加算しない。
独立SOLは今回1呼出し、SDK証拠接続系列で累計5呼出し。各旧receipt・消費枠・指摘を保持する。
一次モデル測定は引き続き0である。

## 再検分待ち

修正版は `sdk-trace-review-v0.6.json` の別有限1回を準備した。
自動承認審査は、新sourceと追加回帰テストを含む6ファイルの具体的payloadへの明示承認不足として拒否した。
拒否されたsource48c4951の送信・起動・予約は0。さらに局所点検した最終source dad596bを送る条件を
`public-code-transmission-approval-request.md` へ明示した。review-06の出力ディレクトリは未作成。
再試行や迂回は行わない。

確認後は修正版の独立静的再検分、親の原応答再照合を優先する。
SDK rawResponseItemの無課金捕捉、任意複数cell/待機、実provider、一次台帳統合、公開canaryと本測定は残る。
固定模擬診断のeligibleForMeasurement=falseを維持する。
