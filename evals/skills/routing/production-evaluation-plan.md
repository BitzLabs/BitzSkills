# 製品本文の一次発火評価への接続

保持集合の独立検分通過後、製品用の実行器を実装する。旧run_model.pyは試作候補を参照するため、
製品本文の測定として起動しない。候補は固定sourceの6本文/71資源manifestに結び付ける。

実行器は次を満たす。

1. ケースID・区分・期待値・比較根拠・保持集合controlをモデル資源へ渡さない。
   モデル入力はprompt/contextと全件共通の指示・イベントカタログに限る。
2. host.pyのlist_resources/read_resourceだけを接続する。モデルのshell、変更、web、apps、
   外部plugin、追加agent、通常のskill自動探索等を無効化し、資源読取り以外の実操作を許さない。
3. 選択した本文の実読取り、固定hash、host一次ログとnative traceの結果対応、最終応答の一致を検査する。
   発火・停止判断と予定イベントを測り、Core操作や行動の実証として扱わない。
4. 固定ref/資源/入力/環境/モデル/反復/上限/停止条件を別有限contractへ記録する。
   一次attemptは起動前に永続台帳へ排他予約し、別出力や再起動による上限回避を拒否する。
5. 各軌跡または固定した検分単位の独立receiptが揃うまで次を起動せず、失敗・中断・不適合で停止する。
   raw bytes・保存失敗時の退避・実exit・可用性と使用量を保存し、自動再試行しない。
6. 保持入力を含む全出力は承認済み非公開領域に新規保存する。公開側は版・件数・hash・集計だけとする。
   provider stderrは公開せず、hashだけを記録する。

初期接続は公開の正例/負例を固定した小さいcanaryから始める。2ケース×2反復の一次最大4を候補とし、
準備と独立検分も別有限枠へ固定する。これは未確定の案で、この文書ではモデルを起動しない。
保持集合の版/hashと実行器の確定sourceを確認してから起動contractを確定する。
canary通過後に公開/保持の分母を広げる別契約を用い、少数結果を全Skill Gateへ拡張しない。
同一条件でのスキルなし比較と行動評価は別の測定範囲として定義する。
異なるモデル系統と実地5種類・配布・最終承認の残件を、SOL限定の発火測定の結果で消さない。

## 2026-10-07 接続前提の確立

保持集合0.5の全12件は、作成者と別のSOLによる経路12/12・新規性1/1・P1=0/P2=0と親の再照合を通過した。
集合仕様source15 `879101449c93df2545bb6c5dcab07664b6d5cdd2`、実行器source19
`33c89531d29d87b6d470a1e61b76d8d2a9a722c5`、ケースSHA-256
`3380c2935bac4b0ed9438ebbfffb3a786d7e7d0acc0ffacefea840a7a79edf25`。
採用範囲は測定準備だけで、一次0・実操作/全Skill Gate未認定。既存authoring contractの残枠は0。
結果は `../results/2026-10-07-single-replacement-reviewed/` に記録した。

製品実行器の最初の実装は、モデル入力から期待値/controlを除く投影と、
host一次ログ/native tool結果/finalの厳密な対応を検査する監査器を優先する。
異なるtool、禁止行為、未読本文、結果/順序/hashの食い違い、正常終端欠落、最終応答不一致は採点せず停止させる。
その後に実CLI接続を閉じたtool構成で検証し、固定source/環境/finite予算/独立検分枠を別contractに記録する。
現時点では一次実行器とその新契約を未実装/未確定として保持し、本計画だけで有料処理は起動しない。

## Phase 4：入力投影・証拠監査コンポーネント

`production_trace.py` は要求と文字列contextだけを投影し、case ID/期待値/区分/controlを転送しない。
CLI0.160.1のexportしたapp-serverスキーマを参照し、原フレームのthread/turn/start/completion/finalと、
実hostのlist/read一次ログを対応させる構造監査を実装した。選択本文のcontent/hash/候補refを照合し、
禁止tool、未知通知、別thread/turn、重複/欠落、未終端、原最終応答不一致を拒否する。
native接続の動作確認はまだ行っていない。合成trace+実hostの対象21試験はこの構造検査だけを証明する。

汎用名hostのimport衝突は初回の全314件で26エラーとなり、専用名の読込みに修正した。
修正後の全314件はOK/exit0。import非汚染の回帰を追加し、対象21件がOK/exit0。
全315件の実結果は後続記録へ保存する。未測定の結果を成功と推定しない。
独立コンポーネント検分は `production-trace-preparation-v0.1.json` の別有限SOL1回に固定する。
公開コードだけを送り、私的評価資料を読まず、一次0/追加委譲0/自動retry0。確定source8と起動前予約を必須にする。

このコンポーネントは入力/catalog/manifestの実行契約束縛、native接続の閉tool検証、一次永続台帳を代替しない。
それらは次の実装・検証対象であり、一次contractと有料canaryをまだ起動しない。

## Phase 4：独立P2指摘の保持と是正

初版source8 `7c556166d7552dc2faed8502b5dddfdc6de94b53` を確定し、clean treeの全315件はOK/exit0だった。
独立SOL1回はP1=0/P2=3で停止した。commentary/最終応答の混同、応答開始後の本文読取り、
実hostと異なるscope/schemaVersionの受入れを、回帰入力で再現した。
原報告/receipt/予約と旧消費1を保持する。公開記録は `../results/2026-10-07-production-trace-review-stopped/`。

修正版は明示的なfinal_answerの一意性とphaseの前後一致、全tool完了後の最終応答開始、以後のtool拒否、
実hostと同じmanifest scope/schemaを要求する。phase欠如/null/未知値は互換推定せず停止する。
局所26件は通過したが、これだけで解消済みとは判定しない。
`production-trace-preparation-v0.2.json` は別source9/公開独立SOL1回/一次0/有料自動retry0に固定する。
新receiptはschemaでキーと値を明示する。旧誤記receiptを修正せず、そのhashを新契約のpreviousFailureへ束縛する。
確定ref/clean treeで全320件を確認し、別文脈で是正と全体を検分してから親が再照合する。
native接続・tool構成・一次台帳と一次モデル測定は、引き続き後続の未実装/未実施範囲である。

### Phase 4：修正版コンポーネントの検証記録

修正版source9 `7fa403a1ade5e1dc6d57f1749bda78fdd397da2c` のclean全320件はOK/exit0。
独立SOL1回はP1=0/P2=0、対象26/全320/敵対8件exit0。親も対象26件を再実行しexit0、原証拠とsource9を照合した。
結果は `../results/2026-10-07-production-trace-remediation-reviewed/`。
検分者自身の最初のguardは初期読取り後だった制限を原receiptと公開記録へ保持する。
親の呼出し前guardと前後のsource一致を確認したが、読取り前要件の代替や完全な検分手順通過とは扱わない。
旧P2=3/原証拠/消費枠を保持する。新枠も消費1/残0、一次0/retry0。
ここでは修正確認を記録するだけで、Phase完了・native接続・行動・Skill Gateを認定しない。
次は実CLI接続/tool実効検証、入力/catalog/manifestの固定契約束縛、一次永続台帳と公開canaryの有限契約。

### Phase 4：CLI通信プローブの隔離条件

`production_cli_probe.py` と `production-cli-probe-v0.1.json` で、CLI0.160.1がResponsesへ提示するtool宣言を捕捉する。
network namespaceを分離し、home全体をtmpfsで隠して、認証/既存設定/私的評価資料をbindもreadもしない。
repoとnode runtimeはread-only、今回新規outputだけを書込み可にする。
実provider認証を要求しない127.0.0.1の模擬Responsesへ最大1要求、公開固定文だけを送る。
模擬最終応答はLOCAL_SIMULATION_ONLY。実CLIの接続・tool宣言の診断に限定し、実モデル測定やnative provider認定に使わない。
一次/有料モデル0。stderrは原bytes保存とhashだけで、復号・出力しない。
shell/multi_agent等をfalseに指定しても、実要求のtool一覧がlist_resources/read_resourceの2件だけでなければ停止する。
停止した設定を一次に流用しない。source5の前後照合と原通信/設定/結果を保存する。
公式根拠は [設定リファレンス](https://learn.chatgpt.com/docs/config-file/config-reference) と
[App Server仕様](https://learn.chatgpt.com/docs/app-server)。設定指定と実効結果を区別する。

### Phase 4：tool宣言の停止と一次台帳コンポーネント

無課金の実CLIプローブ2条件は停止した。模擬turn完了/server exit0でも、2toolだけの宣言を確認できていない。
初版parserはtop-level toolsだけを見たため、input.additional_toolsのnamespace宣言を見落とした。
原要求を残して両方を検査するparserに修正し、Code Mode/agent操作の宣言が残ることを確認した。
feature指定のfalseをtool除外の成功と扱わず、この2条件を有料一次へ接続しない。
この実結果はCLI0.160.1の検証した2条件に限定する。すべての版/設定で不可能とは推定しない。

`production_ledger.py` はケース/catalog/manifest/共通指示/環境の原bytes hashを契約に束縛する。
モデルpayloadは共通指示/catalogとprompt/contextだけ。初期公開canaryの最大2ケース×2反復に限定する。
台帳はgit-common-dirで全worktreeに共通の場所へ固定し、排他lockとO_EXCL予約を起動前に使う。
契約/入力/出力/campaign変更を上限のリセットに使わず、未検分・停止後は次の予約を拒否する。
合成証拠の台帳試験13件とparser/隔離試験8件が局所通過。確定sourceで全341件と独立SOLの別有限1回を検分する。
条件は `production-infrastructure-review-v0.1.json`。公開コードのみ、一次0/自動retry0/追加委譲0。
台帳はproviderを呼ばず、レシートhashの書式だけで実行・独立性・原bytesの意味を認定しない。
製品接続側はsource/runtime/tool構成と原証拠を別に監査し、確認済みの親レシートだけを台帳へ渡す必要がある。
storage引数は隔離試験用で、製品接続は出力先/台帳先を指定できないopen_ledgerだけを使用する。

固定source10 `abfdb8f4aba25a3f4e6b56ec259c29896983a196` でclean全341件OK/exit0、独立SOLはP1=0/P2=0。
読取り前/保存前guard一致、独立13/8/341試験exit0、親21件再実行と原証拠の照合もexit0。
結果は `../results/2026-10-07-production-infrastructure-reviewed/`。この有限枠は消費1/残0、一次0。
公式tag rust-v0.160.1のsource d27764b82f7118f674371e6d6e76271d9d606edbにtool登録前のToolPolicy.allowed_toolsを確認した。
専用adapterまたはmodel情報の別設定は未ビルド/未検証で、一次の起動根拠にはしない。

### Phase 4：公式Python SDKの無課金接続診断（2026-10-08）

公式 `openai-codex==0.160.1` と既存CLI0.160.1を使い、外部通信/認証を遮断した模擬Responsesで2設定を診断した。
正常通信・模擬最終応答は確認できたが、宣言は前回相当10件、agents/対話の明示無効化後も3件で停止した。
3名はfunctions.exec/functions.wait/functions.request_user_input_async。Code Mode内部の全操作を表す件数ではない。
初期SDK引数誤りとuserMessageの誤分類は原記録を保持して修正・別再照合した。
確定source/clean treeの全354試験はOK/exit0、有料0/一次0/独立SOL0。
診断結果と具体的な緩和案は `../results/2026-10-08-python-sdk-probe/report.md`。
候補は2toolだけの宣言条件を緩め、制御用宣言と固定資源の読取り・計算・待機を許容する方式。
内部tool一覧、実list/read、禁止操作、データ可視範囲、Code Mode親子traceを次の無課金契約で検証する。
現在の停止契約/監査器は緩和しておらず、今回の通信通過を実provider/操作制限/Skill Gate/Phase完了に拡張しない。

### Phase 4：緩和案に基づく操作診断（2026-10-08）

ユーザー承認後、表面3宣言を許容し、内部一覧7操作・実hostのlist/read・固定負例を模擬providerで診断した。
hostの読取り属性とMCP2名だけの事前承認を追加。list/readのhost/native/Code Mode結果と本文hashが一致した。
対象外パスはhostで拒否、patchはread-only sandboxで拒否、shell/web/agentの指定entryは存在しなかった。
非同期質問は通常の承認callbackを通らないことを原記録へ保持し、中継でSDK転送前に遮断した。
最終質問試行はHTTP1で停止、namespace内で評価treeの不在を実確認した。
計15試行/29ローカルHTTP要求、有料0/一次0。確定ref/clean全365件OK/exit0、親の全原hash/source/71資源Git照合も通過。
記録は `../results/2026-10-08-operation-probe/report.md`。独立検分と製品実行器は未完。
次はUUIDのSDK/raw Code Mode証拠を製品監査へ接続する。nativeの親call ID欠如を固定1execの対応だけで代替認定しない。
Phase/Step/Gate完了、任意の操作制限、実provider・一次発火成績は今回認定しない。

### Phase 4：SDK原証拠接続と親子ID診断の続報（2026-10-08）

SDKのUUID要求/native通知と模擬Responses原SSEを監査器へ接続した。
CLIの原JSON telemetry19件から固定1execの親call/cell/2子IDを照合した。
指定2targetの対象行を漏れなく原stderrと照合し、前置入力・設定・識別子・順序の偽装を拒否する。
追加mockは3試行/5ローカルHTTP要求、有料0。以前の15試行/29要求とは別計数。
source `f62a87a6181831f87cd24de72c843588869dd736` のclean全416件は61.353s/OK/exit0。
親の原hash/source/全71資源Git/原対象行/親子IDの再照合も通過した。

独立SOL静的検分は4回、各有限1回/一次0/委譲0/retry0。
旧停止と原指摘を保持し、親が再現した条件を順に修正・回帰試験へ追加した。
最新2件のP2はSDK turnのポリシー上書きとRPC応答順序違反で、局所修正まで確認した。
修正版の独立再検分v0.5は、送信対象コードと外部宛先への明示承認不足として自動審査で拒否された。
review-05は未起動/送信0/予約0。独立通過や解消済みとは認定しない。
記録・送信対象5ファイル/hash/宛先/有限1回の条件は `../results/2026-10-08-sdk-trace-connection/`。

確認後は独立再検分と親の原結果照合を優先する。
次の無課金候補はexperimentalRawEventsによるSDK rawResponseItem捕捉で、未着手。
固定1exec以外の複数/yield/wait、実provider、一次台帳との統合、公開canary・本測定が残る。
eligibleForMeasurement=false。Phase/Step/Gate完了・native provider・期待行動・全Skill Gateは未認定。

### Phase 4：JSON型照合の是正と独立再検分待ち（2026-10-08）

ユーザーが具体的な5ファイル/OpenAI gpt-6.1-solへの送信を承認し、review-05を有限1回実施した。
原結果はreview_findings/P2=1/P3=1/CLI exit0。親が原hash/歴史source/終端/schema/usageを再照合した。
数値と真偽値のPython等値比較によるnative本文の偽装、experimentalApiのtrue→1、networkAccessのfalse→0を
同sourceで再現し、型を保つJSON照合へ修正した。host/native/provider/structuredContent/最終応答と
SDK設定/入力/summary/SSEへ適用し、questionsとSSE IDの型・非空条件も検査する。
初期SSE回帰入力の余分な改行を修正し、拒否理由まで確認する対象87件はOK/exit0。
source `dad596b2034bbcd0abb4cd25c19aea78143aa5a3` のclean全426件は61.879s/OK/exit0。
原hash/71資源Git/対象原行/固定1exec親子IDの再照合も通過した。新mock/HTTP0、今回独立SOL1、累計5、一次0/retry0。

修正版の別有限1回v0.6は、新sourceと追加回帰テストを含むpayloadへの明示承認不足として自動審査で拒否された。
送信/起動/予約0。最終sourceの具体的な6ファイル/hash/宛先/有限1回を
`../results/2026-10-08-sdk-json-type-remediation/` に記録し、確認後に独立再検分と親の原結果照合へ進む。
以前の承認待ち・停止・原指摘と消費枠は履歴として保持する。局所通過を解消済み・独立通過とは認定しない。
SDK rawResponseItem捕捉、任意複数cell/待機、実provider、一次台帳統合、公開canary/本測定は残る。
eligibleForMeasurement=false、Phase/Step/Gate完了・native provider・期待行動・全Skill Gateは未認定。

### Phase 4：追加指示と通知外側IDの是正（2026-10-09）

具体的な6ファイル/source/OpenAI gpt-6.1-solへの送信承認後、review-06を有限1回実施した。
原結果はreview_findings/P2=2/CLI exit0。親が原hash/歴史source/guard/終端/schema/usageを再照合した。
合成profileでSDK追加指示を見落とす条件と、turn完了の外側ID矛盾を通す条件を同sourceで再現した。
合成profileでは追加指示のキー指定を拒否し、SDK通知全体と共通nativeの開始/完了で外側IDを照合する。
対象92件はOK/exit0、source `220df0dde378cae10ffc7dc917d84cf1bc5f8f1b` のclean全431件は62.113s/OK/exit0。
原hash/71資源Git/対象原19行/固定1exec親子IDの再照合も通過。新mock/HTTP0、今回独立1・累計6、一次0/retry0。

修正版の別有限1回v0.7は、同じ6ファイルでも新sourceへの送信承認が不足するとして自動審査で拒否された。
送信/起動/予約0。`../results/2026-10-09-sdk-context-remediation/` に今回の6パス/hash/宛先/有限1回と、
以後同じ公開コンポーネント6パスの修正後送信を同じ条件で行う継続確認範囲を記録した。継続範囲は未承認。
確認後は独立再検分と親の原応答照合を優先する。旧停止・指摘・消費枠は保持する。
SDK rawResponseItem捕捉、任意複数cell/待機、実provider、一次台帳統合、公開canary/本測定が残る。
eligibleForMeasurement=false、局所通過を指摘解消済み・Phase/Step/Gate完了・期待行動・全Skill Gateとは判定しない。

### Phase 4：SDK増分・状態・履歴の是正と静的検分通過（2026-10-09）

前の具体的確認資料へのユーザーOKにより、同じ公開6パス/OpenAI gpt-6.1-sol/各有限1回の継続送信が承認された。
review-07〜18の各原結果を保持し、親が再現した増分のライフサイクルと本文矛盾、空入力ID、SSE失敗、
turn開始状態、警告時期/件数、Thread状態/履歴、共通完了要約を是正した。
output_truncatedは同版公式ソースでログプレビューの切詰めと確認し、一律true拒否案を採用せず、型検査と側記録を追加した。
review-17は当該sourceで静的通過。その後親が共通完了要約の追加条件を再現・修正し、
source `a8d0ef2f1398c96affdd54bbdb7bb748efd0c97e` のreview-18もstatic_review_passed/指摘0/CLI exit0となった。
同sourceのclean全460件は62.608s/OK/exit0。原hash/71資源Git/全対象19行/固定1exec親子IDの再照合も通過した。
原応答/schema/usage/歴史Git/guardと試験実出力の記録照合を `../results/2026-10-09-sdk-increment-remediation/` に保存する。
今回独立SOL12・SDK静的系列累計18、新mock/局所HTTP0・一次0・自動retry0。
原usage合計はinput541540/cached6528/output16710/reasoning12606。金額は推定しない。
過去の承認待ち・拒否・停止・指摘・消費枠・局所失敗は当時の履歴として保持する。

次はexperimentalRawEventsによるSDK rawResponseItemの無課金捕捉候補。
任意複数cell/待機、実provider、一次台帳統合、公開canary/本測定は残る。
通過は固定診断コンポーネントの静的検分と局所検証だけ。eligibleForMeasurement=false。
Phase/Step/Gate完了・期待行動・native provider・telemetry本文完全性・全Skill Gateは未認定。

### Phase 4：SDK raw通知の無課金捕捉と独立検分準備（2026-10-09）

Python SDKの公開dict入口からexperimentalRawEvents=trueを指定し、別有限契約read-07/read-08を実行した。
各1試行/局所模擬HTTP2/有料モデル0で、rawResponseItem6件とrawResponse completed2件がSDKへ配送された。
read-07のSDK側ログは整形された複数JSON文書だったため、原bytesを保持し、JSONLへ修正したread-08で再捕捉した。
原RPC外側timestampはSDKが配送しないため保持し、method/paramsを型を保って完全照合する。
raw call/outputはprovider echo/outputへ、MCP本文はhost/nativeへ、71資源Git/原19対象行/固定親cellと2子IDも照合した。
source `4be29c094adb27fe897e72b3d841dcd73b5d0995` のclean全465件は61.858s/OK/exit0。
記録の原bytes/Git再照合も通過。新raw模擬2・局所HTTP計4・有料モデル0、raw独立検分0。

raw ResponseItemは上流SSE bytesではなく、CLI生成id/内部metadataと固定finalの型変換を含む。
原SSEは別保存し、限定投影だけを照合する。全前置文脈・全native lifecycleは認定しない。
既存SDK交換診断は新実験paramsを未知として停止することを実行して確認した。
新raw捕捉コードの独立SOLは未実施。前の具体的継続送信承認の6パスと異なる公開8パスの1回を、
`../results/2026-10-09-sdk-raw-response-capture/` にsource/hash/84547 bytes/宛先/有限条件付きで準備した。
SOL評価すべてへの継続許可で実行を申請したが、自動承認審査は8パス全体の宛先・payloadへの明示承認不足として拒否した。
送信/起動/予約0、専用出力ディレクトリ未作成を確認した。具体的8パスの有限1回への確認を待つ。
確認後に独立静的検分と親の原応答照合へ進む。原ログ・実通知本文は送らない。
raw監査接続、任意複数cell/待機、実provider、一次台帳統合、公開canary/本測定は残る。
eligibleForMeasurement=false、Phase/Step/Gate完了・期待行動・native provider・全Skill Gateは未認定。

### Phase 4：raw捕捉の独立検分と局所是正（2026-10-10）

ユーザーが公開8パスの有限1回を承認し、source4be29cのgpt-6.1-sol静的検分を1回実施した。
CLI exit0、P2が1件。親が原stdio/schema/最終本文/hash/歴史Gitと前/起動/後guard、予約1回を再照合した。
局所完了・final判定がSDK開始thread/turnへ相関していない偽陽性を親が再現し、
同ID、completed状態、null error、固定final本文/phaseとfinal→完了順を検査するよう修正した。
回帰17件/0.095s/OK/exit0。最終確定ref1775038のclean全466件/62.363s/OK/exit0と原捕捉2件の照合も通過した。
途中のPYTHONPATH指定漏れと検証中の記録更新によるclean条件停止は原出力とともに履歴へ保持した。
原結果再照合器もexit0。今回追加SOL1、input32604/output1385/reasoning1034、新mock/局所HTTP0・一次0・retry0。
初回枠は消費済み。是正後の同8公開パス/87851 bytesの追加静的検分1回は
`../results/2026-10-09-sdk-raw-response-capture/public-remediation-code-transmission-approval-request.md` で確認待ち。
追加送信/起動/予約0。局所修正を独立指摘解消済み・Phase/Gate完了と判定しない。
後続のraw監査接続、任意複数cell/待機、実provider、一次台帳統合、公開canary/本測定は残る。

### Phase 4：原証拠照合器の終端検査の是正（2026-10-10）

承認された同8公開パスの追加1回をv0.2/source1775038で実行し、CLI exit0/P2が1件となった。
親が原stdio/schema/応答/hash/usage/歴史Git/前・起動・後guardと予約を再照合した。
P2はcheck_capture自身に成功フラグと原RPC終端の再計算がない点。
固定hashを突破する実ログ改変とは区別し、receipt検証後の合成境界入力で旧関数がfalseフラグを受理することを再現した。
check_terminalを接続し、strict trueフラグ、開始RPC要求ID→応答、thread/turn、turn/started、
final→完了順とnull errorを原RPCから検査する。旧捕捉にも同じ判定を適用し、原ファイルを保持する。
確定ref f8e27f2のclean全469件/62.154s/OK/exit0、原捕捉2件と記録の再照合も通過した。
今回追加SOL1/input33566/output976/reasoning496、raw系列累計2。新mock/局所HTTP0・一次0・retry0。
v0.3の同8公開パス/95935 bytesの追加1回と以後同パス修正版の同条件送信を
`../results/2026-10-09-sdk-raw-response-capture/public-verifier-remediation-code-transmission-approval-request.md` で確認待ち。
追加送信/起動/予約0。指摘解消済み・Phase/Gate完了とは判定しない。

### Phase 4：raw捕捉コード・照合器の静的検分通過（2026-10-10）

ユーザーがv0.3の追加1回と同8公開パス修正版の同条件の継続送信を承認した。
sourcef8e27f2のSOLはstatic_review_passed/指摘0/CLI exit0。親の原応答・hash・歴史Git・guard・有限予約の照合もexit0。
同refの保存済み全469件/62.154s/OK/exit0と旧原捕捉2件の修正判定も適合した。
今回追加SOL1/input35784/output387/reasoning326、raw静的系列累計3。一次0・委譲0・自動retry0。
旧P2/原結果/消費枠を保持する。この静的検分をPhase全体/Gate/実provider/一次測定へ代用しない。
次はSDK raw通知の専用交換監査への接続。既存診断の未知params停止は保持する。

### Phase 4：SDK raw通知の専用交換監査への接続（2026-10-10）

確定ref3cc0690のclean全472件/62.714s/OK/exit0と、公開6パスの独立SOL指摘0/CLI exit0を確認した。
raw flagと既知通知だけを原入力不変の明示投影へ分離し、既存native/MCP本文/provider交換を監査する別入口を追加した。
原RPCとSDK raw配送値を完全照合し、開始RPCのthread/turn、開始完了間のraw、call/output、固定final投影を検査する。
旧入口の未知params停止と、全raw文脈/全native lifecycle/実provider/一次測定の未認定は保持する。
原捕捉2件への適用と原hash/Git/guard/実試験終端/原モデル応答の再照合もexit0。
今回新mock/HTTP/probeモデル0、独立SOL1/input55756/output1047/reasoning991。SDK静的系列累計19、raw捕捉静的系列累計3。
記録は `../results/2026-10-10-sdk-raw-exchange/`。次は固定yield/waitの原証拠捕捉と親セルの継続相関。
eligibleForMeasurement=false、Phase/Gate全体は未認定。

### Phase 4：固定yield/waitの原証拠捕捉（2026-10-10）

source5ddc3c3の局所24件/OK、確定ref全476件/61.854s/OK/exit0。
Python SDKの固定1exec/list/yield/200ms後readとcell_id=1へのwait1回を、新有限契約v0.9で1回捕捉した。
模擬試行1/局所HTTP3/有料モデル0、原RPC raw item8/完了3、全対象telemetry24行を保持する。
開始RPC/終端、原SDK配送値、SSE/provider履歴、一覧/読取り本文とsnapshot71資源を原bytes/Gitへ照合した。
旧親セル監査はwaitを未知callとして停止する。継続相関の専用監査と独立SOL検分は未実施。
同8公開パスのSOL検分は自動承認審査が2回拒否し、起動/送信/予約0。ユーザー本人の具体的送信許可を確認する。
記録は `../results/2026-10-10-sdk-yielded-cell/`。eligibleForMeasurement=false、Phase/Gate全体は未認定。
