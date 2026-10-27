# Phase 4：SDK増分・状態・履歴の是正結果

確定source `a8d0ef2f1398c96affdd54bbdb7bb748efd0c97e` の全460件は62.608s/OK/exit0。
同sourceの独立SOLはstatic_review_passed/指摘0/CLI exit0。親の原結果再照合も通過した。
同じ公開6パスの継続送信は、前回の具体的確認資料に対するユーザーのOKで承認された。
以前の確認待ち・自動審査拒否・停止・指摘・消費枠は、その時点の履歴として保持する。

## 変更

- reasoning/agent増分を開始済みの未完了アイテムへ限定し、index別に累積して完了本文へ照合する。
- SDK入力ID、SSE失敗状態・未知字段、turn開始状態、既知警告の時期と件数を検査する。
- Threadの開始/変更状態、空履歴、ephemeralと、共通監査の完了要約を検査する。
- telemetryのoutput_truncatedを厳密なboolとして検査し、切詰められたプレビューのcall IDを側記録する。

切詰めフラグはログ表示用previewの値であり、実MCP結果の欠落フラグではない。
同版の[公式実装](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/otel/src/tool_result.rs)と、
原read-06の3件がtrueであることを確認した。一律true拒否の提案は採用せず、原値を保持する。
本文は別経路のhost/native/provider原通信で全文照合し、certifiesTelemetryOutputBodies=falseを明示する。

## 独立静的検分の原結果

各契約は1回、追加委譲0・一次0・自動retry0。表の指摘数は原SOL応答を保存した値である。
検分者は試験や原通信の検分を実施していない。親が原stdout/schema/最終応答/usage/Git投影と前後guardを再照合する。

| 回 | 確定source | 原結果 | P2 | P3 |
|---|---|---|---:|---:|
| 7 | `220df0d` | review_findings | 1 | 0 |
| 8 | `8b409f5` | review_findings | 1 | 0 |
| 9 | `7ce4113` | review_findings | 0 | 1 |
| 10 | `28c32c4` | review_findings | 1 | 0 |
| 11 | `e224139` | review_findings | 1 | 0 |
| 12 | `5d12e65` | review_findings | 1 | 0 |
| 13 | `143c27e` | review_findings | 1 | 0 |
| 14 | `57f4719` | review_findings | 1 | 0 |
| 15 | `6150f76` | review_findings | 1 | 0 |
| 16 | `7d0bf57` | review_findings | 1 | 0 |
| 17 | `af7689f` | static_review_passed | 0 | 0 |
| 18 | `a8d0ef2` | static_review_passed | 0 | 0 |

review-12の一律true拒否案は公式実装と原通信を根拠に採用しなかった。非bool値が通る条件は再現して修正した。
review-17は当該sourceの静的検分通過。親が同sourceの共通完了要約に隠れたcommandExecutionを追加して通過する条件を発見し、
さらに修正してreview-18で再検分した。過去のSOL通過を書き換えない。

## Python検証の実出力

最新sourceをclean treeで固定し、次の照合で全試験・原通信・71資源Git・全19対象行・固定1exec/2子IDを検査した。

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py --source a8d0ef2f1398c96affdd54bbdb7bb748efd0c97e
status: sdk_parent_links_artifacts_rechecked
Ran 460 tests in 62.608s
OK
exit: 0
```

| 照合保存先末尾 | 確定source | 件数 | 秒 | exit |
|---|---|---:|---:|---:|
| 09 | `8b409f5` | 439 | 66.649 | 0 |
| 10 | `7ce4113` | 446 | 64.56 | 0 |
| 11 | `28c32c4` | 447 | 63.547 | 0 |
| 12 | `e224139` | 449 | 62.932 | 0 |
| 13 | `5d12e65` | 451 | 64.205 | 0 |
| 14 | `143c27e` | 452 | 63.436 | 0 |
| 15 | `57f4719` | 453 | 63.116 | 0 |
| 16 | `6150f76` | 455 | 63.791 | 0 |
| 17 | `7d0bf57` | 457 | 62.776 | 0 |
| 18 | `af7689f` | 459 | 62.571 | 0 |
| 19 | `a8d0ef2` | 460 | 62.608 | 0 |

局所回帰は段階ごとに追加し、最終121件は1.129s/OK/exit0。
SSE正常系のobject字段の許可漏れと、旧合成warningが開始後に置かれていたための初回試験失敗も記録し、修正後に再実行した。
記録照合スクリプトの初回は、歴史sourceとobservedHeadの無条件一致を要求して停止した。
review-07はsource=220df0d、observedHead=560ab58であり、原guardはheadIsCondition=falseと明記している。
確定sourceの各Git bytes・前後guard一致・observedHeadの実refを照合する原契約に合わせ、原記録を改変せず再検査する。
2回目は再照合スクリプトがJSON要求の原bytesを未解析で渡して停止したため、strict_jsonで解析してから渡すよう修正した。

親call IDはprobe-call、cell IDは1。子IDは原ログの2件を保持し、任意複数cell/yield/waitには一般化しない。
原probe receipt SHA256は `4c60bf95023730815eba9a66aef7e2121d212a3b40ad60dda3a3aac54f5bb311`、最新tests.stderr SHA256は `f2bcb6dae4e44c47a355b519c6493e53a72cdade73a6ff46ab1f024aafcc7e89`。
各原保存物のhash・source・usage・実出力はsummary.jsonへ記録した。

記録照合は次の実出力で確認した。

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-09-sdk-increment-remediation/verify-recorded-results.py
status: recorded_results_match_original_bytes
tests: 460
newIndependentReviews: 12
eligibleForMeasurement: false
exit: 0
```

## 実施回数と残件

今回の独立SOLは12回、SDK静的検分系列の累計は18回。
今回の原usage合計はinput_tokens=541540、cached_input_tokens=6528、output_tokens=16710、reasoning_output_tokens=12606。
金額を推定していない。新mock試行0・新局所HTTP0・一次0・自動retry0。
歴史private検証summaryのnewMockTrials=1/newLocalHttpRequests=2は、再照合した既存read-06の数であり、今回の新規数へ加算しない。

次はSDK experimentalRawEventsの無課金捕捉候補。その後、任意複数cell/待機、実provider、一次台帳統合、公開canary/本測定が残る。
今回の通過は公開6ファイルの固定診断コンポーネントの静的検分と局所検証だけ。
eligibleForMeasurement=false。Phase/Step/Gate完了・期待行動・native provider・全Skill Gateは未認定。
