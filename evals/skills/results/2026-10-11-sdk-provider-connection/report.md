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

## 実接続v0.2の原記録照合

source `e81c0e8fd7d7aa7b148c9810e36bce5c48082736`の全スキル550試験は63.266秒、OK、exit0。
SOL v37は公開コードの静的検分でP2=1（turn/startでのモデル上書き）を指摘した。
送信paramsをthread9キー・turn4キー（無課金故障profileは2キー）に固定し、モデル・指示・sandboxの上書き拒否を両profileの回帰へ追加した。
この是正の独立再確認は残件である。

別名providerでSDK1 turnの実接続原記録を取得した。namespace/processはexit0、timeoutなし。
26原artifact、15 rollout events、共通予約、固定source、原RPC・API・最終JSON・schema・usageを親が再照合した。
初期client request JSONの5入力はdeveloper/developer/developer/user/userで、公開固定入力と制御metadata3宣言を確認した。
API合計は3件で、モデル一覧取得2件・モデル推論1件。旧契約の「API合計1件」は未達として保持する。
入力2,635・出力22・合計2,657トークンは原SDK通知とrolloutで一致した。
HTTP/SSE wire全文・server内部入力・認証復旧ゼロ・API事前hard capは認定しない。
初回失敗の予約を保持し、実接続v0.2の有限予約を別に消費した。同じ診断を再起動しない。

source `a37bd2118c373021bc8f4b6a29e8bfc410f35f98`の全スキル554試験は62.698秒、OK、exit0。
SOL v38はv37のturn上書き是正に指摘せず、原requestの固定文字列の部分一致についてP2=1を指摘した。
原requestではBASEはdeveloper位置1/content全体、DEVELOPERはdeveloper位置2/content先頭、PROMPTはuser位置4/content全体に完全一致する。
この構造を照合器へ束縛し、追記と位置交換を拒否する合成回帰を追加した。
v38の原応答・使用量・固定Git source・共通予約を親が再照合する。是正の独立再確認は残件である。
同じ接続診断を再実行せず、保存した原記録を修正後の照合器で検査する。

routing一次評価、5種類実地比較、Skill Gate 4、Phase 4完了は未認定。
