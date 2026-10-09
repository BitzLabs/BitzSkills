# Phase 4：Python SDK raw応答通知の無課金捕捉

確定source `4be29c094adb27fe897e72b3d841dcd73b5d0995` の全465件は61.858s/OK/exit0。
新旧捕捉の原証拠と公開要約の照合も通過した。2026-10-10の独立SOL静的検分でP2が1件出た。
親が偽陽性を再現して局所判定を修正した。是正後の独立再検分は未実施。

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

## 残る検査と初回送信承認の履歴

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

この拒否と未送信状態は2026-10-09時点の履歴である。2026-10-10にユーザーが8パスの有限1回へOKと回答した。
その後、独立静的検分と親の原応答再照合を実施した。後続のraw監査への接続、任意複数cell/待機、
実provider、一次台帳統合、公開canary/本測定へ進む。
eligibleForMeasurement=false。Phase/Step/Gate完了・期待行動・native provider・全Skill Gateは未認定。

## 独立検分と局所是正（2026-10-10）

source `4be29c094adb27fe897e72b3d841dcd73b5d0995` の8公開ファイルをgpt-6.1-solへ1回送信した。
CLI exit0/timeoutなし、verdict=findings、P2が1件。一次0・委譲0・自動retry0。
input32604/cached0/output1385/reasoning1034。金額は推定しない。
原receipt SHA256は `803eeef684dc44c30898894a8eb3f58b6a5e93139a395210da5522d8ffd067b4`、
原response SHA256は `f9be6b602926781506bdc031bc7f7ce1d36d9e1598adcf721982b0e7458b3855`。
親が原stdio/hash、応答schemaと最終本文、前/起動/後の同一source guard、歴史Git、予約1回を再照合した。

P2はoperation probeの完了・final判定がSDKで開始したthread/turnへ相関していないこと。
親が別thread/turn・非null turn.error・完了→final順の合成入力で旧2フラグがtrueになることを再現した。
SDK開始結果のIDを保持し、固定最終回答の本文・phase、同thread/turn、completed状態、null error、
final→完了順をすべて満たす場合だけ両フラグをtrueにするよう修正した。
回帰17件/0.095s/OK/exit0。旧read-07/read-08の原RPCも修正後の判定に適合した。
この再照合は新mock/局所HTTP/有料モデルを増やさず、原捕捉結果を再分類・上書きしていない。

全件試験の初回は検証コマンドで必要なPYTHONPATHを指定し忘れ、466件/44.187s/44errors/exit1になった。
標準のPYTHONPATHとPYTHONDONTWRITEBYTECODEを指定した再実行は466件/62.463s/OK/exit0。
初回失敗を成功と扱わない。
是正後の同8パスは別有限契約v0.2で静的再検分1回を準備する。初回v0.1の1回は消費済み。
現時点で是正の独立再検分・SDK raw監査接続・Phase全体の完了は認定していない。

確定ref `1775038798653da9a6801ea0402c22febae2273a` の最終検証1回目は、試験466件/62.137s/OKだったが、
実行中に親が記録照合ファイルを更新してclean tree条件を満たさず、verification source drift/exit1で停止した。
原stdout/stderrを `.venv/production-sdk-raw-response-verification-02` に保持した。
変更を戻して同確定refのclean状態で新保存先03へ再実行し、全466件/62.363s/OK/exit0、
原捕捉2件・前後同一source guard・clean treeをすべて確認した。
最終summary SHA256は `5deb0b24ab50525eb1e71778e0dc2d5da1a92dd904d8b1e55d6de10780736014`。
記録照合器はこの原bytes・実試験終端・歴史Git、元P2の拒否、旧原捕捉への修正判定の適用も再検査する。

追加1回の[具体的な送信範囲](public-remediation-code-transmission-approval-request.md)は、
同8公開パス/確定ref1775038/87851 bytes/OpenAI gpt-6.1-sol/一次0/委譲0/retry0。
新保存先02は未作成であり、追加の送信・起動・予約0。今回は明示承認された初回1回だけを実施した。
