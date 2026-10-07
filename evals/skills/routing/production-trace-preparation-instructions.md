# Phase 4：製品入力投影・証拠監査器の独立SOL検分

呼出しメッセージで指定した40桁sourceと準備契約のsourceFilesを固定して検分する。
実装者と別の文脈で公開コードだけを読む。私的ケース/期待値/報告/raw traceと認証情報は読まない。
追加のモデル・agent・外部サービス・一次測定を起動しない。ソースは編集しない。
全コマンドの作業ディレクトリは呼出しで指定した統合worktreeへ明示する。mainで作業しない。

今回の範囲はモデル入力の `prompt/context` 投影と、app-server形式の原フレームを想定した構造監査。
実モデル接続・閉じたtool構成・永続一次台帳・入力/manifest/catalogの実行契約への束縛は後続の未実装範囲である。
合成traceと実hostを用いる単体試験の通過を、実native接続・一次測定・行動・Skill Gateの証拠としない。
その制限内でも偽装証拠を通す経路、入力漏洩、未読本文の認定、最終応答/終端の取り違えがあれば指摘する。

検分観点:

- 期待値/ID/区分/controlをモデル投影へ追加しないこと。元contextを参照共有しないこと。
- 公開hostのlog/result仕様と整合し、manifest追加情報がdiscoveryへ混入しないこと。
- read本文/hash/候補ref、host/native tool・arguments・結果・件数の対応が厳密であること。
- 別thread/turn、未終端、禁止tool、失敗、中断、重複、未知のフレーム、最終応答不一致を拒否すること。
- 製品6名を超える旧aggregateエントリと不正path/eventsを採点しないこと。
- 他のhostモジュールをimportで汚染しないこと。合成入力と実操作の認定を区別すること。

実際にsource_guard.verify(worktree, source, contract.sourceFiles)を検分前後に実行する。
呼出しで指定したPython3.12/jsonschema環境で、契約の対象件数と全skills件数を実行し、実exitと要約を記録する。
P1/P2を検分し、契約outputsのrootRelativePath内の `review.md` と `receipt.json` に新規保存する。
既存ファイルと予約を上書き/削除しない。
receiptはoutputs.receiptSchemaを読み、自分でもJSON Schemaへ照合する。
例えば数値はキー末尾へ付けず、`"independentReviewerSolConsumed": 1`、
`"primaryModelTrajectories": 0`、`"automaticRetries": 0`、`"delegations": 0` と記録する。
phase4/sourceCommit/status/severityCounts/actualTestCounts/actualTestExitCodes/sourceGuards/reportSha256と、
nativeProviderBytesAvailable/certifiesNativeConnection/Behavior/SkillGate/ProductCompletionのfalseを必須とする。
保存はO_EXCLによる新規、0700のroot内に0600で行う。既存の原報告と予約を上書きしない。
previousFailureがあれば、その報告/receipt/予約hashと原P2指摘を確認し、旧消費枠を返却しない。
最終応答phaseはfinal_answerの明示を必須とし、欠如/null/未知値は停止するという互換方針に従う。
最終応答開始時に全toolが完了し、以後toolが発生しないことと、実host同等のmanifest scope/schemaを特に検分する。
指摘は公開ファイルの実行/データ条件とfile/lineに結び付ける。修正案まで示し、修正は実装者へ戻す。
最終応答は件数とstatusの集計だけを返す。親が試験とhash/sourceを再実行するまでは作業完了を認定しない。
