# Phase 4：実provider接続の着手条件

2026-10-11時点。draft。送信はPhase 4期間中の本人許可済み。以下は起動許可や認定の代替ではない。

| 条件 | 現在の証拠 | 残作業 |
|---|---|---|
| 入力・snapshot・共通台帳 | 既存の固定入力束縛、共通一次/独立予約、原記録照合 | 実行経路への接続 |
| 全初期入力の観測 | 局所rollout traceの要求3件が原HTTP要求JSONと一致、初期5 items | 実providerの原traceとcaller/RPCの照合 |
| 要求回数・retry | 公式固定版の通常retry以外の経路を確認 | 故障注入と実効上限の検証 |
| 原応答の観測 | SDK rawとnative完了、局所SSEあり | traceの投影差異を保持して実providerへ接続 |
| 隔離 | 模擬診断でhome/保持評価資料/ネットワークを隔離 | 実通信の差分と宛先の検分 |
| 行動・実地・比較 | 統合実装の局所回帰のみ | 一次評価、5種実地比較、Skill Gate 4 |

固定上流refは`d27764b82f7118f674371e6d6e76271d9d606edb`（CLI0.160.1）。調査した経路：

- `model-provider-info/src/lib.rs`のrequest_max_retries/stream_max_retriesは、通常のretry設定。
- `core/src/responses_retry.rs`は、設定上限到達後にもWebSocketからHTTPへのfallbackを試す。
- 同ファイルのUnboundedConnectionRetries分岐は通常の上限検査より前にあり、接続失敗の継続再試行を許す。
- `features/src/lib.rs`では`unbounded_connection_retries`が既定true。
- `core/src/client.rs`のHTTP経路は401等の認証復旧後に別のloopで再要求する。通常retry0だけでこの経路の0回を証明しない。
- `login/src/auth/manager.rs`には認証復旧の状態遷移がある。認証値を読まずに公開実装だけを調査した。

次の無課金故障注入では、認証なしの隔離模擬providerを用い、HTTP失敗・stream切断・接続失敗を別条件にする。
通常retry0、stream retry0、supports_websockets=false、unbounded_connection_retries=falseの候補設定で
原要求件数・失敗終端・timeout・子process終了を観測する。正常ケースだけで上限を認定しない。
固定版のsystem_proxy_fallbackも既定trueであることをfeatures/src/lib.rsで確認した。
候補設定ではsystem_proxy_fallback/respect_system_proxyもfalseとし、通常経路以外の再接続を別に扱う。
認証復旧の0回や実providerの上限は、この無認証実験から認定せず別に残す。

rollout traceはHTTP要求直前のJSON値を保存する候補であり、認証ヘッダーを読むproxyは用意しない。
局所の要求JSON値一致を上流HTTP bytes一致へ拡張しない。保存はbest-effortなので欠落を成功へ補完しない。
出力traceはprotocol投影で、元SSEのstatus/annotationsとの差異がある。全応答bytesを取得したとは扱わない。
