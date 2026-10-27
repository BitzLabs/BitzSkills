# Phase 4：SDK原証拠接続と親子ID診断（2026-10-08）

SDKのUUID要求・native通知・模擬Responses・host記録を監査器へ接続した。
確定source `f62a87a6181831f87cd24de72c843588869dd736` の全416件と原証拠再照合は通過した。
最新修正の独立SOL再検分は、コード送信の自動承認審査で拒否され、未起動である。
修正候補の局所検証までを記録し、指摘の解消済み判定は保留する。

## 実装と診断範囲

`production_sdk_trace.py` は原ログを変更せず、SDKのUUIDを派生した要求IDへ対応付ける。
初期化・thread/turn設定、単一入力、開始/完了、delta、明示的最終応答、未知操作・質問を検査する。
送信した模擬SSEを原bytesで保存し、provider要求・固定exec本文・MCPのlist/read・本文hash・最終応答を照合した。
模擬診断に限定し、任意providerへの互換性を推定しない。

CLIの指定2targetの原JSON stderrから、対象行を漏れなく保存する。
原19イベントにより親call `probe-call`、cell `1`、2つのnative子IDを照合した。
範囲は固定1execと逐次list→readの2呼出しであり、複数cell・yield/waitは未認定である。
指定target以外のstructured logも原stderrに保持するが、この対応診断の選択対象には含めない。

実SDKの前置contextを含む入力の検査は、SDK/CLI0.160.1・2026-10-08の局所固定条件に束縛した。
応答順序ではinitialize/thread応答の先行を要求し、正常なturn/startedの先行通知は許容する。
turn要求のポリシー上書き、未知フィールド、原対象行の欠落、矛盾した識別子や親子イベント順序を拒否する回帰試験を追加した。

## 原証拠と実検証

今回追加した無課金模擬試行は3件、ローカルHTTP要求は5件。以前の15試行/29要求に混ぜて数えない。

| 保存先（リポジトリ内） | 結果 |
|---|---|
| `.venv/production-operation-read-05` | HTTP2、host2、正常模擬終端・最終応答一致、SDK/namespace exit0 |
| `.venv/production-operation-user-input-stop-05` | HTTP1、host0、非同期質問をSDK転送前に遮断、TransportClosedError、通常turn未完、CLI/namespace exit0 |
| `.venv/production-operation-read-06` | HTTP2、host2、親子IDの原telemetry19件、正常模擬終端、SDK/namespace exit0 |

認証と外部通信を遮断し、隔離namespace内で.git/.spec/tests/docs/evals/skills/resultsの不在を実確認した。
snapshotの71資源を固定Git refへ照合した。mockに有料モデル呼出しはない。
独立SOLは下記4回を別計数し、作業全体を有料0とは表現しない。

最新再照合コマンド：

```sh
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py --source f62a87a6181831f87cd24de72c843588869dd736
```

実出力は `sdk_parent_links_artifacts_rechecked`、`tests.count=416`、`tests.seconds=61.353`、`tests.exitCode=0`。
原テストstderr終端は `Ran 416 tests in 61.353s` / `OK`。
原hash、対象telemetry全行、親子対応、sourceの前後一致、71資源を確認した。
保存先は `.venv/production-sdk-parent-links-verification-05`。

公開要約の再照合もPythonのみで実行した：

```sh
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-08-sdk-trace-connection/verify-recorded-results.py
```

実出力は `recorded_results_match_original_bytes`、tests416/mockTrials3/localHttpRequests5/independentReviews4/
pendingReviewInvocations0/eligibleForMeasurement=false、exit0。
原テスト終端・各原artifact hash・歴史source・独立最終応答とschema・usage・旧停止・送信候補bytesを再照合する。
このコマンドは外部通信・モデル起動・書込み・全テスト再実行を行わない。

- 再照合summary SHA256：`ec692d4e72cfc86d8ea52b538dd0992769dfe5f8f00e1f1139f6f83e3361be89`
- テストstderr SHA256：`1478ed8425215afe63cb81188db7e56c37f753b26e5fe459e300233545c04460`
- 原親子試行source：`558104ec2557f735658f17ef3a8d097167f3c0d3`
- 原receipt SHA256：`4c60bf95023730815eba9a66aef7e2121d212a3b40ad60dda3a3aac54f5bb311`

SDK接続初回再照合ではsource `e903ef14f6729e979ae1a961eadf1a7517320912` の391件/62.552s/exit0も保存した。
最初の親子照合は既存の旧354件用保存先と衝突してFileExistsError/exit1で停止した。
既存記録を変更せず、専用の `production-sdk-parent-links-verification-*` を作成した。
再照合summary内のnewMockTrialsは照合対象の原試行を指す。同じ原試行の再照合を新規モデル呼出し・新規試行へ加算しない。

## 独立検分と修正履歴

公開コードだけの独立したCLI文脈で、SOLを4回呼び出した。
それぞれ有限1回、一次0、追加委譲0、自動retry0。旧予約・stdout・stderr・receipt・応答を保持した。
親が原stdout/最終応答/hash/source guardを再照合した。検分者の試験実行や原実行証拠の検証とは扱わない。

| 独立保存先末尾 | source先頭 | receipt状態 | 原応答のP2/P3 |
|---|---|---|---|
| `review-01` | `2ce51de64` | review_stopped（起動errorの受入れ条件違反） | 2 / 1 |
| `review-02` | `55bd64eb5` | review_findings | 4 / 0 |
| `review-03` | `f530be223` | review_findings | 1 / 0 |
| `review-04` | `09875b5cd` | review_findings | 2 / 0 |

各行の指摘は異なる修正段階に対するもの。未解消件数として単純に合算しない。
review-01は原応答の指摘を再現・修正したが、停止receiptを通過へ訂正しない。
Code Modeを無効化した起動時の固定警告だけを、turn開始前・1件・完全一致条件で別版から許容した。
deprecated featureによる別errorは削除後の新契約で扱い、未知errorを一律に無視しない。

前置入力の偽装、SDK入力との不一致、final ID欠落、親子識別子の矛盾、順序違反、対象原行の欠落を親が再現した。
最新review-04のP2はturn開始要求のポリシー上書きとRPC応答の並べ替えであり、source f62a87aで許可フィールドと先行関係を修正した。
全416件通過は局所証拠であり、独立再検分を代替しない。
詳細は `../../routing/sdk-trace-review-remediation.md` と本結果の `summary.json`。

## 再検分待ちと次の工程

`sdk-trace-review-v0.5.json` はsource f62a87aの5ファイルと固定検分指示/公開schemaを
OpenAI Codex CLIの `gpt-6.1-sol` へ送る独立静的検分1回を用意した。
自動承認審査は「送信対象コードと宛先への明示的な機密データ送信承認が不足」として実行を拒否した。
外部送信・プロセス起動・予約は行われず、出力ディレクトリreview-05も未作成。再試行や迂回はしない。
送信対象・hash・宛先・保存先・上限は `public-code-transmission-approval-request.md` に示す。

確認後は有限1回の独立再検分、親による原結果再照合を優先する。
次の候補はexperimentalRawEventsによるSDK rawResponseItemの無課金捕捉であり、未着手・未検証である。
実provider接続、任意複数cell/待機の監査、一次台帳との統合、公開canaryと本測定が残る。
eligibleForMeasurement=false、Phase/Step/Gate完了・期待行動・native provider・全Skill Gateは未認定である。
