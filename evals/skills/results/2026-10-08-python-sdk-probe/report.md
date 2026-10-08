# Phase 4：公式Python SDKの接続診断と制限緩和案

2026-10-08。目的は製品スキルの発火測定に使う接続方式の診断。
公式Python SDK `openai-codex==0.160.1` と既存CLI `0.160.1` を使った。
検証コードはPython。既存CLIとLinuxのbubblewrapは必要だが、Rust/Node.jsでの追加実装・ビルドは行っていない。
SDKのCLI runtime依存を追加せず、明示した既存CLIを起動した。
この版/2設定だけの結果で、全SDK/全版での可否を結論しない。

## 実結果

| 設定 | ローカルHTTP要求 | 宣言数 | 通信・模擬最終応答 | 2toolだけの宣言 |
|---|---:|---:|---|---|
| 前回相当・SDK経由 | 1 | 10 | 原通信の再照合で通過 | 未達、停止 |
| agents/対話を明示無効化・SDK経由 | 1 | 3 | 通過 | 未達、停止 |

後者の宣言は `functions.exec`、`functions.wait`、`functions.request_user_input_async`。
`agents.enabled=false`、`features.multi_agent_v2=false`、
`tools.experimental_request_user_input.enabled=false`、`tools.update_plan.enabled=false` を追加した。
モデル名・モデルmetadataは変更していない。MCP起動ready、正常turn終端、模擬最終応答一致、CLI実exit0を確認した。
この3宣言はモデルへ提示された表面のtool inventoryであり、Code Mode内部の全操作一覧ではない。
MCP readyも、モデルが製品本文を読んだ証明には使わない。

全スキル試験は確定ref/clean treeで実 `Ran 354 tests in 61.360s / OK`、exit0。
うちSDKプローブの停止判定・依存改変・承認拒否・通知分類の回帰は13件。
全試験原stdout/stderrとhashは `.venv/production-sdk-parent-verification-01/`。
コマンドは [summary.json](summary.json) に記録した。
有料モデル0、一次軌跡0、独立SOL検分0。実provider接続・禁止操作の実拒否・行動・Skill Gateは未認定。
Phase 4/Step/Gateの完了判定は行っていない。

## 原記録と修正の保持

- 初回native条件はsandbox内の隔離起動で停止。provider要求0。
- 初回minimal条件はSDK `turn_start` の引数誤りでTypeError。thread開始まででprovider要求0。
- 呼出しを `turn_start(thread_id, input_items)`、通知をturn専用queueに修正した。
- native再試行は正常通信だったが、初期診断器が `userMessage` を操作と誤分類した。
  原receiptのprotocol=falseを上書きせず、修正版で同じ原bytesを再照合しprotocol=trueを別記録した。
  2tool未達という停止判定は変わらない。
- 全試験の初期起動はuv cache書込み、jsonschema依存/PYTHONPATH不足で停止・失敗した。
  CI指定と同じ依存・PYTHONPATH、リポジトリ内cacheで修正し、最終全354件を保存した。

通信を行ったnative sourceは `6c9f9f56b81b9eeda667ae90f3550157ca77c68e`、
minimal/診断器sourceは `4fe057a52c455853673a8a4e9467147dd6885474`。
親の再照合script sourceは `8caf4da41813975edaeb6439642a43992ee3eade`。
旧原receipt/通信/namespace stderrは保持し、stderr本文は公開しない。
各receiptと原要求/traceのSHA-256をsummaryへ記録した。
全sourceの開始/終了guard、Git原bytesのhash、receipt内の原artifact hashを再照合した。
依存tree hashは契約へ固定した。CLIバイナリのビルド再現性はこの診断範囲に含めない。

## 推奨する緩和案

緩める条件は「宣言が2toolだけ」の一点とする。
今回残ったCode Modeの制御用宣言を許容し、固定資源の一覧・本文読取りと、
それに必要な計算・待機だけを評価の許容操作にする。
これは次の検証条件の提案であり、現在の停止契約や証拠監査器を成功に変更するものではない。

| 対象 | 次の検証での条件 |
|---|---|
| 表面の宣言 | 検証済み3名を固定。新しい宣言があれば停止 |
| `exec` / `wait` | 資源読取りの呼出し・結果整形・待機を許容。内部で呼べる全操作を別途捕捉 |
| `request_user_input_async` | 宣言は許容、呼出しは採点せず停止。無人評価へユーザー回答を混入させない |
| 読取り | 固定manifestの資源だけ。hostのpath/hash検査を継続 |
| shell/変更/web/apps/追加agent | 引き続き対象外。設定値だけで無効化を認定しない |
| データ隔離 | モデルの可視領域を候補snapshotと必要runtimeに絞る。期待値/control/台帳を見せない |
| 外部通信 | 無課金検証はnetwork namespaceで遮断。将来の実モデル接続は承認済みprovider宛だけを別検証 |
| 証拠 | host log/native trace/final/原bytes/hash/順序一致を維持。Code Modeの親子呼出しも対応づける |
| 費用・停止 | 別有限契約、起動前台帳、目的外呼出し・失敗・欠落で停止、自動有料retryなし |

サンドボックスと監査を合わせて使う。監査による事後検出は、dispatch前の拒否を証明しない。
書込み/外部通信を隔離境界で拒否できることと、参照できるデータの範囲を次の実験で確認する。
既存の全リポジトリread-only mountを、そのままモデル向け隔離の完成形とは扱わない。

## 次の無課金検証

1. SDKと模擬ResponsesからCode Modeを1回実行し、内部操作一覧を捕捉する。
2. 実hostのlist/readを行い、本文hashとnativeの親子traceを照合する。
3. 目的外のshell/patch/外部通信/追加agent/対話要求を固定した負例で試し、
   実操作の拒否または採点前停止を区別して記録する。合成拒否だけを実拒否と認定しない。
4. 内部操作を十分に制御できなければ、Python Responses/Agents SDKで2関数を管理する方式を比較する。
   この場合はCodex native harness同等性を緩める別条件となるため、SDK接続結果と混同しない。
5. 独立コンテキストの検分と有限SOL canary契約を確定してから一次モデル測定へ進む。

今回はSDK診断と提案まで。製品6本文の発火成績、スキルなし比較、行動/実地/異系統/配布/最終承認は残る。

## 公式根拠

OpenAI DocsでPython SDKがapp-serverをJSON-RPCで制御し、既存CLIを指定できることを確認した。
[Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)、[App Server](https://learn.chatgpt.com/docs/app-server)。
ツールの宣言・実行環境は別に設定する。[Using tools](https://developers.openai.com/api/docs/guides/tools)。
