# Phase 4：Python SDK raw応答通知の無課金捕捉

確定source `4be29c094adb27fe897e72b3d841dcd73b5d0995` の全465件は61.858s/OK/exit0。
新旧捕捉の原証拠と公開要約の照合も通過した。新規捕捉コードの独立SOL静的検分は未実施。

## 捕捉結果

Python SDK 0.160.1の公開dict入口でexperimentalRawEvents=trueを送信した。
同版公式source `d27764b82f7118f674371e6d6e76271d9d606edb` の
[ThreadStartParams](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/app-server-protocol/src/protocol/v2/thread.rs)と
[通知名](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/app-server-protocol/src/protocol/common.rs)を確認した。
SDK生成型から除外された実験字段をSDK公開dictへ指定し、原rpc-inでtrueが送られたことを検査した。

| 試行 | source | 原結果 | raw item | raw completed | 局所HTTP | 有料モデル |
|---|---|---|---:|---:|---:|---:|
| read-07 | `c026dab` | operation_diagnostic_captured | 6 | 2 | 2 | 0 |
| read-08 | `e232222` | operation_diagnostic_captured | 6 | 2 | 2 | 0 |

固定1exec内のlist→readだけを実行した。bwrapで外部ネットワーク、repoの.git/.spec/tests/docs/evals結果を隠蔽し、
認証情報をmountせず、専用保存先だけを書込み可能にした。各契約は1試行・HTTP最大2件・有料モデル0。
原SSE/RPC/stdioとsource/hashを専用保存先へ保持し、旧試行を上書きしない。

raw itemの内訳はdeveloperメッセージ1、userメッセージ2、custom_tool_call1、custom_tool_call_output1、assistantメッセージ1。
6件ともPython SDKへ配送された。raw completed通知2件も配送された。
原RPCとSDK配送値のmethod/paramsは型を保って完全一致した。
外側のemittedAtMsはSDKへ配送されないため、原RPCに保持し、比較用投影だけから除いた。
raw call/outputの生成id・本文はproviderのecho/outputへ相関し、providerのMCP本文をhost/native結果へ照合した。
71資源のGit/hash、全target原19行、固定親cellと2子IDも検査した。

## 保存形式の是正

read-07ではSDK配送値を既存の整形JSON関数で保存し、.jsonlという名前でも複数行のJSON文書列になっていた。
通知の欠落はなく、旧原bytesを変更せず明示的な複数JSON文書として解析・照合した。
1通知1行のJSONLへ修正して別契約read-08で再捕捉した。改行を含む日本語、NaN拒否、欠落/型ずれ/逆順の回帰を追加した。
各型の単体試験は最終16件/0.089s/OK/exit0。

原契約はdriverがJSONの固定エンコードで保存するため、Gitの体裁そのままのbytesとは異なる。
初回の局所照合はこの体裁差を拒否して停止し、確定Gitを同じ固定エンコードへ投影して照合するよう修正した。
原保存物を作り直したり上書きしたりしていない。

## 検証の実出力

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-artifacts.py --source 4be29c094adb27fe897e72b3d841dcd73b5d0995
status: raw_capture_artifacts_rechecked
Ran 465 tests in 61.858s
OK
exit: 0
```

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py
status: recorded_raw_capture_results_match_original_bytes
tests: 465
rawItemsPerCapture: 6
rawCompletedPerCapture: 2
mockTrials: 2
localMockHttpRequests: 4
rawMockPaidModelCalls: 0
pendingReviewInvocations: 0
eligibleForMeasurement: false
exit: 0
```

試験出力・原receipt・各artifact・前後source guard・確定Gitのhashをsummary.jsonに記録した。
今回の新規raw模擬試行は2、局所HTTPは計4、有料モデル0。再照合は新規mockやHTTPを増やさない。
直前のSDK診断是正系列の独立SOLは累計18回であり、raw捕捉の新規独立検分は0回。
これらを同じ「モデル0」とまとめない。

## 残る検査と送信対象

raw ResponseItemは上流SSE bytesそのものではなく、CLIが生成id・内部metadataを加え、
固定finalのstatus/annotationsを変換した別の型である。原SSEは別に保持し、明示した限定投影へ照合する。
raw入力通知はproviderの全前置文脈を網羅するとは認定しない。
既存SDK交換診断はexperimentalRawEventsを未知paramsとして停止することも実行して確認した。
現時点では新raw形式をその監査へ接続しておらず、捕捉通過を既存診断・一次測定へ代用しない。

新捕捉コードと原証拠照合器の独立静的検分1回を準備した。
対象は[具体的な公開8ファイル](public-code-transmission-approval-request.md)、合計84547 bytesと固定指示/schema。
前の具体的継続送信承認はSDK診断の6パスであり、この8パスはその対象外。
宛先はOpenAI Codex CLI/gpt-6.1-sol、1回上限・一次0・追加委譲0・自動retry0。
原ログ・実際の通知本文・snapshot・認証情報を送らない。

SOL評価すべてへの継続許可を根拠に、この公開8パスの有限1回を起動する処理を申請したが、
自動承認審査が「明示承認済みの6パスを超え、8ファイル全体の宛先・payloadへの承認が確認できない」と拒否した。
送信/起動/予約0。専用出力ディレクトリが存在しないことを実際に確認した。
回避経路や間接実行を使わず、[具体的8パス/source/hash/宛先/有限1回](public-code-transmission-approval-request.md)への確認を待つ。

確認後は独立静的検分と親の原応答再照合を優先する。その後、raw監査への接続、任意複数cell/待機、
実provider、一次台帳統合、公開canary/本測定へ進む。
eligibleForMeasurement=false。Phase/Step/Gate完了・期待行動・native provider・全Skill Gateは未認定。
