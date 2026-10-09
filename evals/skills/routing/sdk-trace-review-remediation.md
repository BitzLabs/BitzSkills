# Phase 4：SDK診断の指摘と是正候補

初版静的検分source `2ce51de64a7721ab08f4c7a431563c477f4382a4` の別SOL応答はP2=2/P3=1だった。
CLIの2つの起動エラー通知（廃止featureとCode Modeの意図的無効化）を受入れ器が拒否したため、
原receiptのreview_stoppedを保持し、通過と訂正しない。原最終JSONの3指摘は親が同じsourceで実行して再現した。
旧有限枠は消費1/残0。原receipt・応答・stdioを変更しない。

- P2：前後provider prefixが同じでも、SDKとは別のユーザー本文で診断が通る。
  修正候補は最初のprovider要求の最終user messageをSDKのturn/start原入力へ一致させる。
- P2：結果イベントに矛盾するcell/runtime/turn/sourceを足しても親子ID診断が通る。
  修正候補はresult/result_ready内の追加識別フィールドを受領済みの識別へ照合する。
- P3：final item IDとdelta item IDの両方を欠落させてもNone同士で一致する。
  修正候補は非空IDを必須化し、provider final IDとnative final IDも照合する。

3条件を回帰へ追加した。修正確認は別の独立SOL有限1回の静的検分と親の原証拠照合で行う。
静的検分者は試験を実行せず、親が入力送信前のsourceを照合して確定bytesを送る。
Code Mode無効化の既知エラーはturn開始前の完全一致1通知だけを原hash付きで保持する。
未知エラー・turn開始後のエラー・tool実行・複数turnは引き続き停止させる。
これは任意の実行、実provider、一次採点、全Skill Gate、Phase完了の認定ではない。

## 2回目の静的検分からの是正候補

source `55bd64eb55baaf00d0ba8b366b5fbc7fd7cec0e7` の別SOLはP2=4。
旧3指摘の修正後にも、同じprefixへの追加user message、dispatchの操作識別矛盾、
子操作同士の逆順、選択ログが原stderrの部分列でしかない条件を親が実行して再現した。
原receiptのreview_findings、応答、消費1/残0を保持する。

是正候補は、SDK原入力だけでなく前置メッセージも固定すること、dispatchの操作識別を照合すること、
逐次list→readをnative/telemetry両方で要求すること、全対象ログを原stderrから完全抽出して照合すること。
検証済みのSDK0.160.1/局所mock provider/2026-10-08の自動文脈は、明示形と資源hashに束縛する。
試験用の合成入力は単一user messageだけの別profileとし、文脈を補完・推定して受理しない。
一般のprovider/別日/複数cellへの互換性を今回認定しない。

## 3回目の静的検分からの是正候補

source `f530be22340d7e9bd26dc524dce993ef31a1ac7e` の別SOLはP2=1。
親execの受領へ矛盾したcell_idを追加してもID診断が通ることを親が同sourceで再現した。
修正候補はdirect受領を固定7フィールドへ限定し、cell/runtime/未知フィールドを拒否すること。
結果のtool_origin/mcp_tool/counterも、存在する場合は既知の呼出し識別と一致させる。
旧記録、消費1/残0を保持し、別有限SOL1回で修正版を静的検分する。

## 4回目の静的検分からの是正候補

source `09875b5cd948ab1d9e6253ae15cc8a247aaed727` の別SOLはP2=2。
turn/startにapprovalPolicy/sandboxPolicyを追加した条件と、initialize応答を通知より後ろへ移す条件を
親が同sourceで再現した。修正候補はSDK要求フィールドの明示と応答順序の検査。
thread/startの応答をturn開始通知に先行させ、turn/startedがturn/start応答に先行する正常形は許容する。
元記録と消費1/残0を保持し、別の有限SOL1回で静的検分する。

## 5回目の静的検分からの是正候補

送信対象5ファイル/OpenAI Codex CLI gpt-6.1-sol/有限1回のユーザー明示承認後、
source `f62a87a6181831f87cd24de72c843588869dd736` を別SOLで静的検分した。
P2=1/P3=1、原receiptはreview_findings。旧拒否記録を取消・訂正しない。
親が同sourceで、candidateVersionの数値1→trueをnative結果へ混入した条件、
experimentalApiのtrue→1、networkAccessのfalse→0を実行して診断通過を再現した。

是正候補は型を保つJSON照合の共通化。objectのキー順序だけを正規化し、
bool/int/floatを区別してhost/native/provider/structuredContent/最終応答へ適用する。
SDK能力・sandbox・user/summary/prefix/設定・SSEアイテム照合にも同じ条件を使う。
SSEの出力/content indexと原telemetryのattempt/status codeは整数型を要求する。
元記録、消費1/残0を保持し、局所試験通過を独立解消判定の代替にしない。

同じ型の検査漏れを防ぐため、questionsの未指定/null/空配列と0/false/空文字/空objectを区別する。
模擬SSEのresponse IDにも非空文字列を要求する。型・識別子の回帰試験を追加する。

## 6回目の静的検分からの是正候補

6ファイル/確定source/OpenAI Codex CLI gpt-6.1-sol/有限1回の送信承認後、
source `dad596b2034bbcd0abb4cd25c19aea78143aa5a3` を別SOLで検分し、P2=2を得た。
親が同sourceで、cwdなしprofileへのbaseInstructions追加と、turn/completed外側turnIdの矛盾を
diagnose_exchangeが通す条件を実行して再現した。原review_findings、消費1/残0を保持する。

合成の単一user profileではbaseInstructions/developerInstructionsの指定を拒否する。
SDK通知全体で存在する外側threadId/turnIdを確定IDへ照合し、共通native監査でも
thread開始・turn開始・完了の外側ID矛盾を拒否する。空/nullの追加指示、開始時の矛盾も回帰へ追加する。
局所通過を独立解消判定・Phase完了・一次評価・任意provider認定の代替にしない。

## 7回目の静的検分からの是正候補

同じ6ファイルの公開修正版/OpenAI gpt-6.1-sol/各有限1回の送信と再検分を、ユーザーが今回と以後について承認した。
source `220df0dde378cae10ffc7dc917d84cf1bc5f8f1b` の別SOLはP2=1。
親が同sourceで、turn終了後の未知reasoning IDへのtextDeltaを診断が通す条件を実行して再現した。
原review_findings、旧消費1/残0、以前の送信拒否記録を保持する。

固定SDK0.160.1の公式generated/v2_all.pyで3種類のreasoning増分とagent増分の必須フィールドを確認した。
共通native監査で、同じturnの開始済み・未完了の適切な型のアイテムにだけ増分を許可する。
未知ID・開始前・完了後・turn終了後・別型ID・欠落/未知字段・非文字列delta・非整数/負indexを拒否する。
正しいreasoning開始→増分→完了も回帰に含める。reasoning本文の意味や一次測定を認定しない。
同じ6ファイル・同じ宛先の別有限1回で修正版を検分し、親が原結果を再照合する。

## 8回目の静的検分からの是正候補

source `8b409f5c9e549da732f36cb7e6e41ce80a5ff20c` の同6ファイルの別SOLはP2=1。
親が同sourceで、reasoning textDeltaだけを改変し、完了contentを変えない矛盾が診断通過する条件を再現した。
原review_findings、消費1/残0を保持する。

開始時のcontent/summaryを原アイテムと共有せずコピーし、indexごとの増分を累積して完了本文へ型を保って照合する。
summaryの新規partは末尾追加だけ、textDeltaの新規contentは次のindexだけを許容し、穴・重複partを拒否する。
SDK0.160.1のnullable/省略本文を勝手に空配列へ補完せず、開始本文が不明なchannelの増分は停止する。
既存本文または増分があるchannelを照合し、増分を送らない空の開始→全文完了という既存の合成形式は保持する。
共通agent増分にも本文照合を適用する。意味の採点・期待行動・一次測定・Phase完了を認定しない。

## 9回目の静的検分からの是正候補

source `7ce4113a7f4a2170d1222d79e436ccc829fdee15` の同6ファイルの別SOLはP3=1。
親が同sourceでuserMessage開始/完了のIDを空文字列へ置換して診断通過する条件を再現した。
共通監査へ渡す前に保持通知へ分離される入力にも、SDK入口で非空文字列IDを要求する。
原review_findings・消費1/残0を保持し、空IDの両通知を含む回帰を追加する。

## 10回目の静的検分からの是正候補

source `28c32c4afb206fcc227dce58448a59e43d72f526` の同6ファイルの別SOLはP2=1。
親が同sourceで固定SSEのresponse.completedへ非nullのerrorを追加して交換診断通過する条件を再現した。
呼出し/最終応答のcreated/completed両境界でerrorとincomplete_detailsの未指定/nullだけを許可する。
固定SSEとして列挙したevent・response・最終item字段以外も拒否し、未知の失敗証拠を捨てない。
non-nullの真偽値・空文字・空配列も拒否し、null正常系と未知字段の回帰を含める。
実provider一般形式へ拡張せず、原review_findings・消費1/残0を保持する。

## 11回目の静的検分からの是正候補

source `e2241395027e514cca1a64e6cb1a554006781e8f` の同6ファイルの別SOLはP2=1。
親が同sourceでturn/start応答だけをstatus=failed・error非nullへ変えて診断通過する条件を再現した。
共通検査をSDK開始応答とnative開始応答/通知へ適用し、inProgress・空items・errorなしを要求する。
開始turnの未知字段、完了時刻/所要時間、非整数開始時刻、欠落statusも拒否する。
合成fixtureの開始状態を明示し、原SDK応答を作り直さず照合する。原指摘と有限消費枠は保持する。

## 12回目の静的検分の再検証と限定

source `5d12e6590fa5f91c1dd3f777abb750329e70e883` の同6ファイルの別SOLはP2=1。
指摘はoutput_truncated=trueを出力本文の欠落と解釈し、一律拒否を提案した。
しかし原read-06の3件はすべてtrueで、SDK native/host/providerの結果本文を別経路で全文照合している。
同版の公式実装はこの値をログ表示用preview.truncatedから取り、output_lengthは元output.len()から取る。
参照: https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/otel/src/tool_result.rs
このため「trueなら本文が欠ける」という指摘の前提と一律拒否案は採用しない。原指摘・消費1/残0は保持する。

親が同sourceで文字列falseも通る型の欠落を再現した。字段がある場合は厳密なboolを要求する。
trueのcall IDを結果へ側記録し、certifiesTelemetryOutputBodies=falseを明示する。
親子ID・順序は完全保存したtarget原行で検査し、本文はhost/native/provider原通信を使う。
プレビューから本文完全性を認定せず、原ログのtrueをfalseへ変更しない。型/true/falseの回帰を含める。

## 13回目の静的検分からの是正候補

source `143c27ecc41d6cc73bef14cb96c2b25471cc1a40` の同6ファイルの別SOLはP2=1。
上のCode Mode無効化エラーの限定はreviewer CLIの起動イベントであり、SDK warning通知とは別である。
ただし親はSDKの既知warningをturn完了後に2件追加して通過する条件を同sourceで再現した。
固定SDK warningも本文1種類・開始前1件だけへ限定し、重複/開始後/終了後と不正allowlistを拒否する。
原通知を消さず側記録し、CLI起動エラーのhash許容をこの警告へ流用しない。原指摘と消費枠は保持する。

## 14回目の静的検分からの是正候補

source `57f47199bd81a799ad1401c06b232872fe988cf1` の同6ファイルの別SOLはP2=1。
親が同sourceでturn完了後にthread/status/changedのsystemErrorを追加して通過する条件を再現した。
thread状態は専用分岐で字段と状態を検査し、idle・待機flagなしactive・開始前notLoadedだけを許可する。
systemError・未知状態・待機flag・余分な字段・終了後activeを拒否する。
完了後idle正常系を保持し、共通監査/SDKの回帰を追加する。原指摘と消費枠を保持する。

## 15回目の静的検分からの是正候補

source `6150f7686b0dfb060b76d2c4d9275fa3283f2fab` の同6ファイルの別SOLはP2=1。
親が同sourceでthread/start応答とthread/startedオブジェクトにsystemErrorを指定して通過する条件を再現した。
Thread.statusがある場合は、開始応答・開始通知・状態変更通知に同じ共通検査を適用する。
欠落statusの従来合成形式は保持し、存在するエラー/未知/待機状態を捨てず拒否する。
各開始経路と両経路同時の回帰を追加する。原指摘と消費枠を保持する。
