# Phase 4：無認証providerの通信故障診断

固定source `10926fe16ec838bce633bf12611cc74bb76090c6`、公式Python SDK/CLI 0.160.1を使用。
4条件を各1回、各30秒以内、ネットワーク名前空間内の局所HTTPだけで実行した。
有料モデル・routing一次評価は0。私的原ファイルは公開せず、hashと再照合器を記録する。

| 条件 | 局所HTTP受信 | API試行 | 結果 |
|---|---:|---:|---|
| HTTP 503 / retry 0 | 1 | 1 | SDK turn failed、process終了0 |
| HTTP 503 / retry 1（対照） | 2 | 2 | SDK turn failed、process終了0 |
| stream切断 / retry 0 | 1 | 1 | SDK turn failed、process終了0 |
| 接続失敗 / retry 0 | 0 | 1 | SDK turn failed、process終了0 |

通常/stream retry、WebSocket、無制限接続再試行、system proxy fallbackを明示設定した。
原receipt・全artifact・固定Git source・設定・SDK turnの文脈・原stderrからのAPIログ投影を再照合する。
503のretry 1対照で試行が増え、retry 0で増えなかったことを観測した。

これは無認証の局所条件の結果である。実OpenAI接続・認証復旧・任意故障でのHTTP要求数の
事前保証・Skill Gate・Phase 4完了は認定しない。次に、別予約の最小実接続診断で原入力と
API試行・終端を観測する。局所診断の成功を実サービス評価へ代用しない。
