# Phase 4：Python SDK raw通知の専用交換監査への接続

確定ref `3cc0690505c64951b06816fd5ae0272051351067` のclean全472件は62.714s/OK/exit0。
同refの公開6パスの独立SOLはstatic_review_passed/指摘0/CLI exit0。
親が原応答と原試験出力、歴史Git/source guard、旧捕捉2件への新入口の適用を再照合した。

## 変更と原証拠

diagnose_raw_exchangeを既存SDK交換監査と別の入口として追加した。
strict trueの実験flagを確認し、原入力を変更せず、raw flagと既知raw通知だけを明示投影へ分離する。
既存native/MCP本文/provider交換監査を通した後、開始RPCに相関するthread/turn、開始完了間のraw通知、
固定個数/順序/字段/整数時刻/一意ID/internal turn IDを検査する。
原RPCのraw method/paramsとSDK配送値は型を保って完全一致を要求し、call/outputをprovider echo/outputへ、
finalを明示したResponseItem投影へ照合する。外側timestampは原RPCに保持する。
SDK生成環境は検査者が明示する既知日だけを選び、旧既定の10月8日を維持し、原raw試行は10月9日で照合する。
元のSDK交換入口はexperimentalRawEventsを未知paramsとして停止する挙動を保持する。

旧read-07/read-08の原receipt/artifact hashと歴史Git、71資源、MCP本文、全19target行/親cell/2子IDを確認した。
両捕捉はraw item6/raw completed2で、新しい交換監査も通過した。
旧整形JSON文書列を改変せず別形式として読み、read-08はJSONLとして読む。
新SDK模擬試行0・局所HTTP0・有料probe0。既存2試行/HTTP4を新しい試行数へ付け替えない。

接続の最初の照合は、旧環境文の固定日と新原証拠の日の差で停止した。
次はraw developer入力をbaseInstructionsと取り違えて停止した。
原値の差分が日だけであることと、raw入力のprovider内ID対応を確認し、検査者指定日とSDK補足文脈へ投影を修正した。
SDK raw入力通知はadditional_tools/baseInstructions全体を網羅しない。それらは既存交換監査で別途照合する。
内部metadataはturn IDと字段型だけ。rawは上流SSE bytesそのものとは認定しない。

## 検証と独立検分

局所SDK試験77件/0.725s/OK/exit0。欠落/改変/追加SDK配送値、別context、逆順、本文/応答ID不一致、
重複item ID、非整数時刻/内部非有限時刻、未知metadata、開始完了外のrawを拒否する回帰を追加した。
Pythonの原証拠検査と全試験は次のコマンドで通過した。

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py --source 3cc0690505c64951b06816fd5ae0272051351067 --raw-exchange
status: sdk_raw_exchange_artifacts_rechecked
Ran 472 tests in 62.714s
OK
exit: 0
```

既承認の公開6パスの継続送信範囲で、新しい有限v0.19/独立SOL1回を実施した。
一次0・追加委譲0・自動retry0、原ログ/実通知本文/snapshot/認証内容は送信していない。
input55756/cached0/output1047/reasoning991。SDK静的系列累計19、raw捕捉静的系列累計3と区別する。
原stdio/schema/最終JSON/実exit/usageを保持し、親が原hashと前/起動/後guard・有限予約・歴史Gitを照合した。

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-10-sdk-raw-exchange/verify-recorded-results.py
status: recorded_raw_exchange_results_match_original_bytes
tests: 472
capturesReplayed: 2
rawItemsPerCapture: 6
newMockTrials: 0
newLocalHttpRequests: 0
independentSolInvocations: 1
reviewFindings: 0
eligibleForMeasurement: false
exit: 0
```

原hash/確定ref/安全な結果投影と実usageはsummary.jsonに記録する。通知本文と原ログを公開記録へコピーしない。
全raw文脈・全native lifecycle・任意複数cell/待機・実provider・一次台帳・全Skill Gate・Phase全体は未認定。
次は固定yield/waitの原証拠捕捉と親セルの継続相関。eligibleForMeasurement=falseを維持する。
