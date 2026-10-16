# 保持12ケース・24枠の評価接続

状態: 入力準備を実装中。実行器・有限台帳・開始前独立検分が揃うまでモデルを起動しない。

公開92枠の実行・記録は完了した。保持集合は独立意味検分を通過した
`production-routing-held-out-0.5.0` の12件をそのまま採用する。
ケース原bytes SHA-256は `3380c2935bac4b0ed9438ebbfffb3a786d7e7d0acc0ffacefea840a7a79edf25`。
公開結果 `results/2026-10-07-single-replacement-reviewed/summary.json` をGitの確定refで直接照合し、
新しい入力契約のhashへ束縛する。集合・期待値・採点基準を現行評価中に修正しない。

## 入力準備

`production_heldout_inputs.py` は公開92枠の入力束縛とは別の部品である。
全sourceのGit blobと作業ファイルを照合してから、承認済みcollection-05のケース原bytesを内部だけで読む。
絶対path全成分のsymlink、最終fileのhardlink、所有者・権限・サイズ不適合、同じfdの読取り前後の変化を拒否する。
非公開値を含むJSON/schema診断をそのまま出力しない。

12件を原順序のSE-1200〜1211に固定し、各2反復、一次24・独立24・retry0・delegation0とする。
全mandatory、区分の分母と6機能ごとの正例/負例・停止境界の対を確認する。
モデルpayloadは公開評価と同じ共通指示・イベントcatalogと各ケースのprompt/contextだけ。
caseId/category/capability/mode/mandatory/expectedと来歴・集合controlを渡さない。
親側の内部slotには採点に必要なIDを残すが、公開出力へ含めない。

```text
python -B evals/skills/routing/production_heldout_inputs.py --source <確定40桁commit>
```

この入口の出力は集合版・件数・hash・状態だけで、ケース保存・モデル起動・予約はすべて0。
入力準備の成功を、開始許可・測定成功・独立意味採点・Skill Gateへ読み替えない。

## 後続の実行条件

1. 公開評価時と同じ製品72資源の全bytes、共通指示・catalog・protocol・schema、固定CLI/SDK/runtime、
   当日の校正・環境を照合し、新しい確定refの専用契約へ束縛する。
   集合採用時の旧71資源と現在の評価対象72資源を同一候補の測定として合算しない。
2. 新規campaign、24枠の固定順序、一次/独立各24、有限timeout、retry0/delegation0とする。
   collection-05内の新規owner-only領域を唯一の証拠保存先とし、既存資料を書き換えない。
   台帳・予約・入力契約・payload・原軌跡・採点・親の照合をすべて非公開に保存する。
   別output/worktree/refで消費枠を返却できない共有の識別と排他制御が必要。
3. 一次モデルはprompt/contextだけをケース固有入力とする。独立採点は別文脈で原証拠と期待値を照合し、
   親が原bytes/hashを再確認してから次へ進む。危険操作・drift・不正原記録は全体停止。
   安全な誤選択は不正解、証拠が不足する個別取得失敗は評価失敗として分母に残す。
   個別失敗の封印と次枠の許可には現物資源の前/起動直前/後一致が必須で、失敗した枠の再試行は行わない。
4. 本番入口は最大2枠の自然終了単位とし、各論理起動は60秒以上離す。
   準備・独立検分・利用枠・認証・非公開の送信先/送信範囲を確認してから起動する。
   入力準備への読取り承認だけで、新たな外部送信を承認済みと推定しない。
5. 公開へは集合版・件数・hash・集計だけを保存する。ケース単位のID、選択結果、期待値、payload、
   native/SDK/Host原bytes、stderr本文、私的な保存物の一覧を公開しない。

## 終了後

公開92・保持24の実施/失敗/欠測を区別して検分し、その後に失敗原因と送信内訳を整理する。
失敗対策とコンテキスト削減は別変更・同条件比較とし、正しい動作・安全性・完了性を保つ。
今回誤った動作や評価失敗を再現することを合格条件にしない。
初期入力だけでなく追加取得を含む総入力・cache・取得回数・時間・正解/不正解/評価失敗を比較する。


## 専用台帳の部品（実行器は未接続）

`production_heldout_ledger.py` は非公開collection-05内の固定共有namespaceへ、
契約とhash鎖付きjournalを新規追記する。既存の契約・eventを上書きしない。
`open_shared` の保存先にworktree/ref/output引数はなく、別条件で既存契約を再初期化しない。
クラスの任意root引数は隔離試験用で、本番接続は固定factoryを用いる。

一次予約→起動marker→一次取得→独立予約→独立marker→独立取得→親照合の順序を固定する。
前枠が未了の間は次を拒否し、予約・起動markerを実provider呼出し数と同一視しない。
親照合は正解と不正解を別に記録する。個別失敗は起動markerの後だけ封印でき、
契約に一致する現物資源proofと失敗原証拠のhashを必須にする。正常測定へは変換しない。
全体停止は別eventで記録し、再開・追加eventを拒否する。

全操作は所有者限定のdirectoryとfile、NOFOLLOW/単一link、排他lock、
契約/順序/分母/前event hashの再検査を経る。途中保存の破損・不明file・journal欠番を拒否する。
台帳が受け取る原hashの意味・安全性は後続の取得/採点/親adapterで検査しなければならない。
この台帳の合成試験通過だけで、本番起動や非公開送信を許可しない。


## 実行条件と開始前資源検査の部品（モデル入口は未接続）

`production_heldout_execution.py` は保持専用version、24一次/24独立、
固定source、入力契約/配備原bytes/hash、CLI0.160.1、有限timeout、retry0/delegation0を束縛する。
公開の92枠versionやpublic campaign、公開.venv保存先を受理しない。
保存先は承認済みcollection-05の `measurements/<campaign>/primary|independent/attempt-NNNN` に限定する。
配備snapshotは確定refから新規に準備し、評価中に固定した製品72資源を全件含める。

`production_heldout_preflight.py` は入力部品・台帳・この実行/配備検査を含む
公開sourceのGit blob/現物一致を先に検査する。一次payloadの共通部分もGitに束縛する。
snapshotの全資源・Git一覧・原bytes、SDKの全宣言fileと閉じた一覧、
固定Node/CLI、当日contextと原校正を既存の中立な検証器で再照合する。
全公開資源/校正が成立した後だけ、採用済み非公開集合の原bytesを内部再照合する。
proofは実行条件・配備・入力契約へ束縛し、そのhashを専用台帳の条件へ接続する。

これらの部品はnamespace起動・台帳予約・証拠保存を行わない。
`ledger_contract` は渡されたproofの識別子を束縛するだけで、proofの現物成立を自己認定しない。
本番adapterは起動前/直前/後に `verify_resources` を再実行し、
開始前の独立検分と原軌跡の全照合を別に要求する。


公開92枠から継続する現評価では、保持用の新refのGitと一致するだけでは不十分である。
preflightは公開製品固定source `b00589bac9bd9dc1f96a9e8b9f71654cad4af5e3` から
全72資源の一覧・原blobを直接取得し、新refとsnapshotの原bytesの両方へ照合する。
同数の製品へ変更してhashを取り直しても拒否する。この検査は製品の意味判定や保持内容からの最適化を行わない。


## 一次worker・原照合・局所隔離（親operatorは未接続）

`production_heldout_launch.py` は固定された単一stageだけを書込み可にするargvを組み立てる。
/home・/root・/tmp・/runを隠し、公開コード/SDK/runtime/snapshotだけを読取り専用で戻す。
コーパス・期待値・Git・評価結果をmountしない。標準CLI認証は不透明な読取り専用委譲だけとし、
agentが内容の読取り/コピー/hashをしない。processのumaskは077を要求する。
一次identityからcaseIdを除き、モデルには共通指示/catalogとprompt/contextだけを渡す。

`production_heldout_capture.py` はnamespace内部だけのSDK workerである。
現物/入力/hash・source/campaign・24上限、実argv、SDK/runtime/72資源、canonical schemaと
具体的開始前独立検分の原report/隔離proofを検査してからSDKへ進む。
通常ホストからの直接起動はGit/評価コーパス可視性を拒否する。
未知SDK要求は拒否し、原SDK proxy/Host/controlの観測上限を既存のまま使う。
private値を含む例外本文をstdout/stderrへ展開しない。

`production_heldout_evidence.py` は保持専用のimmutableな原bytesを束縛する。
同一slotの入力・identity・実argv/config・runtime/SDK・開始前検分・三時点資源proof・最終終端を検査し、
中立のnative/Host/control/rollout検証器で実内容を相関する。
public matrixのBoundExecution/receipt/92分母への変換はしない。
戻り値には私的判断やusageが含まれるため、公開側は別に件数/hash/集計へ投影する。

`production_heldout_originals.py` は固定private stageの既知原一覧だけを読む。
全原名/型/linkを内容消費前に検査し、owner-only 0700/0600、NOFOLLOW、同一fdの前後状態、
原hashと型付き条件を照合する。opaqueなcodex-home/logs/state等の内容には入らない。
原は最大512file、各64MiB/計256MiBまでとし、上限超過を正常測定へ変換しない。

`production_heldout_isolation.py` は公開の合成要求1件だけを保存する別局所probeである。
実構成から標準認証mountを除き、network namespaceを分離し、SDK/model/台帳予約0で
private corpusと認証の不可視性・公開資源の実bytes・argvを確認する。
この一次限定proofは、一次と独立の全pipeline開始許可には使えない。
親の有料operator、独立採点・親確定・具体的開始前検分は未接続である。


## 保持独立意味採点の原bytes境界（2026-10-17）

production_heldout_semantic.pyは保持専用型から12件×2の採点入力と応答を束縛する。一次原payloadに期待値を追加しない。採点入力は同じ枠の固定期待・実Host/control結果・native最終・機械指標を含み、原receipt/実行/入力/期待値hashをbindingsで返させる。保持IDと24上限をschemaへ固定し、公開92枠のtype/headerは再利用しない。

選択（6スキルではselectedPath=null）・outcome・必要/禁止イベントは従来と同じ機械指標で判定し、semantic=passを加えてaccuracyとする。安全な誤選択はmeasured_incorrect候補、安全fail/unknown・内容integrity未確認はstopped候補。原ファイルの直接照合は親、内容の意味/安全は独立検分者の責務。原応答一致とusageは構造照合だけで、実モデル起動や台帳確定は別の原記録検査を要する。期待値/本文/採点結果はprivateとして扱い、戻り値を公開ログへ出さない。


## 一次親operatorと起動原記録（2026-10-17）

production_heldout_operator.run_primaryは具体的な全pipeline開始前独立検分と現物資源proofを先に要求する。共通private台帳のlockを保持して予約し、固定stageをEXCLで新規作成する。正常一次は三時点proof/原loader/SDK native/rollout照合後にのみprimary_capturedとなる。一次正常をparent_verifiedへ置換しない。独立起動と親確定のadapterは別工程。

logical-pacing.jsonはreceiptの原inventoryに含める。次の論理起動は直前のstarted markerとcaptured/failed journalのreceipt hashから原pacing/control hashを再照合し、単調時計60秒以上を確認する。時計逆行・原改変は停止する。provider内部のHTTP間隔/実行回数を示す証明ではない。

失敗原も既知固定名と有限rollout pathを先に列挙し、owner-only/NOFOLLOWで読む。認証opaqueはmetadataだけ。正常/失敗とも上書き・再起動・予約返却はなく、同一三時点proofの単回取得失敗だけprimary_failedへ封印する。stop marker/未知file・directory/原不正/資源drift/保存失敗はglobal_stopとなる。失敗を正解や不正解の分母へ足さない。
