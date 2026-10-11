# Phase 4：SDK接続診断の起動失敗

source `86db7ca7f965366c9d7e2ebab1ccf83faf577286`の全スキル547試験は62.867秒、OK、exit0。
有限の別接続予約1枠を消費し、公開固定入力のSDK診断を1回起動した。
CLI 0.160.1は組込み`openai` providerの上書きを禁止し、設定読込みでexit1となった。
SDK側はTransportClosedError、namespaceはexit0、timeoutなし。原受信RPC・APIログは空で、モデル要求前の停止である。
消費した予約を返金せず、同じ契約を再起動しない。

公開コードの独立SOL検分はv33〜36の計4回。P2は順に3/2/2/1件で、原指摘と消費を保持した。
v33の追加送信・重複reply・固定故障API期待値、v34のid-onlyと故障caller相関、v35のdeltaとthread順序に対応した。
v36はinitialize応答より前のthread開始の見落としを指摘した。独立再確認は残件である。
全試験・原応答・共通予約・固定Git sourceの親再照合を別に行う。静的検分を実軌跡の検分へ代用しない。

起動失敗から、無認証のモデル要求なし初期化検査を先に追加する。
組込みproviderを上書きせず、公式CLIの別名provider設定でOpenAIの標準認証・接続先とretry設定を検証する。
任意の送信先や認証headerを設定するproxyは作らない。成果物は明示した原記録だけをhash集計する。
元receiptにある`codex-home/auth.json`はbwrapの空のmount先（host側size0）であり、再照合器は内容を読まない。

無課金startup0.1はSDK起動前のNETLINK_ROUTE権限停止、startup0.2はnetwork隔離を維持した必要権限で
initialize/initializedのみを実行し、SDKエラーなし・process終了0・APIログ空を原照合した。
別名providerの設定読込みは確認できた。認証・実接続の成功を意味しない。
source `ede0b4876f413f758e810e289c5f75c13db89ce6`の全スキル549試験は62.767秒、OK、exit0。
是正版接続v0.2は元失敗と無課金初期化のhashを先に固定し、同じ旧枠を再起動せず、別の有限1枠へ設定是正を結ぶ。

実OpenAIモデル接続、初期入力捕捉、routing一次評価、5種類実地比較、Skill Gate 4、Phase 4完了は未認定。
