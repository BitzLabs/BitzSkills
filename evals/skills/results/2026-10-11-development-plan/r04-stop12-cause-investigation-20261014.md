# 新04・12件目の停止原因調査（2026-10-14）

独立採点のCodex CLIがHTTP 429 / Too Many Requestsを報告して異常終了し、再試行0回の固定条件に従って評価回が恒久停止した。制限の詳細な種類は未確定。

| 確認項目 | 結果 |
|---|---|
| 一次評価12 | 正常終了。models取得2件・Responses3件は記録上HTTP200 |
| 独立採点12 | 1回起動、exit1、約4.712秒、タイムアウトなし。応答/usage/正常終端なし |
| 停止経路 | CLIエラー→非正常終端の検査でValueError→independent-capture-failed→以降を停止 |
| 成功1〜11との設定比較 | 保存先以外は一致。前後の資源も一致 |
| 入力比較 | 直前成功61,932byte、停止62,192byte。260byte差の因果は未証明 |
| 詳細な制限情報 | 既知error.code、Retry-After、応答エラーbody、endpointは採点traceにない。request-IDのラベルはあるが値は公開しない |
| 調査時の利用枠 | 同じLinux CLIの2026-10-14 18:41:53 JST観測でChatGPT認証、5時間53%・週間86%、上限到達種別なし |
| 現在の正常復帰 | 利用枠読み取り成功だけではResponses正常復帰を証明できない。停止当時とのaccount identity比較も未実施 |

停止時の具体的な制限・同時利用・サーバー側混雑は、この記録だけでは特定できない。HTTP429を週間枠の使い切り、API残高不足、認証失効のどれかへ推測で割り当てない。一般APIの429にも複数の分類があるため、詳細コードでの識別が必要（[公式資料](https://developers.openai.com/api/docs/guides/error-codes)）。今回のChatGPT認証への適用は別途証拠が必要。

現在の状態は[公式のaccount/rateLimits/read](https://learn.chatgpt.com/docs/app-server)でモデル起動なしに確認。最初の診断用helperはCLI起動引数、次はJSONL送信形式に問題があり未完了だった。その原を保持して形式を修正した3番目のhelperで読み取りが成功した。これらは停止した評価の再試行ではなく、モデル起動0の別診断である。

次の対処は、失敗時の安全な診断項目（HTTP status、取得できるerror.code/Retry-After、ローカル照会用ID）を保存する方針と開始前確認を整えること。旧新04は再開せず、具体開始前検分が済んだ新しい評価回で正常実行を確認する。サーバー側への照会は未送信。使用量・費用の不明値を0にしない。

独立検分と親の全hash/bytes再照合済み。製品コード・採点条件・原の成績・停止状態を変更せず、新05は未開始。詳細: [r04-stop12-cause-investigation-20261014.json](r04-stop12-cause-investigation-20261014.json)。証跡archive全31regular members、SHA `261968f98d4ba0929a58038e44c6b9767e8ea15dd59c9b505563142b8cbdf4d5`。
