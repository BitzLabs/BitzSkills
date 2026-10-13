# 開発計画の開始とR01の是正確認

対象計画は提案31。2026-10-11に利用者が採用し、保存と各作業の開始前の表記を指示した。

## R01の原独立検分

基準source `64aed6cc116e2aeefc41039adad41ba15e7f0360`、v40の公開4本文、SOL最大1回・300秒・一次0・retry0。
原結果はP1=0/P2=2/P3=0、CLI exit0、timeoutなし、review_findings。原response/receiptを隣接JSONに保存した。
親は原trace/final/Schema/source guard/共有予約/usageを再照合した。指摘を成功へ置換しない。
使用量はinput 21,009、cached 0、output 1,341（reasoning 714はoutputの内数）。請求金額は未確定。

監視設定の欠落でstderr callbackが呼ばれない経路と、未知tool_sourceで制御通知を受理する経路を指摘された。
回帰で再現し、既知tracingをCLI起動前とcanary policyで要求すること、direct/code_mode子の既知通知だけを許可し未知sourceを停止することを実装した。
callbackなしの旧模擬profileは任意tracingと結果の2キー形式を維持する。

## 是正後の別検分

検証用detached Worktreeの確定ref `955c4db248b842673aa57575924f80dce7c43e56` で、全567試験はOK/exit0。
作業者と別文脈の検分者が差分と原指摘を確認し、cleanな同refで関連33試験を再実行した（0.514秒、OK/exit0）。前後のclean状態と3ファイルhashも一致し、是正を妨げる追加指摘なし。
これは2件の是正確認と旧profileの局所互換性に限る。実provider/送信前hard cap/全行動/Skill Gate/Phaseは認定しない。

## 初回停止と環境

検分用Worktreeの試験用一時領域不足による初回563件の30 errorsと原出力を保持した。領域を補い別ログで全563件が通過した。
固定CLIパスは実体0.162.1へ更新されていたため、repo内へ公式0.160.1をinstall scriptsなしで導入し、読取り専用mountで契約パスへ提示した。グローバルCLIは変更していない。
最初の外側mountは/dev/nullが読取り専用になり、予約前のGit確認で停止した。/devと/proc、一時領域の前提を補い、予約未消費を再確認してから1回を起動した。起動前停止はモデル再試行ではない。

## 残件

R02は一次SDK profileと原結果・独立採点・台帳の接続を進める。R03の一次カナリアは0件。
計画・進捗・修正は対象Worktreeに保存している。integrationブランチのHEADは64aed6cc、修正の検証用refはdetachedのローカル記録。pushは実施していない。

## R02: 一次SDK profileのコンポーネント確認

`production_sdk_trace.requests/normalized` と `production_canary_trace.audit` にpublic-canaryを明示追加した。旧diagnosticは従来の入力を維持する。一次threadの完全なキー集合・raw events true・固定モデル/provider、一次turnのキー集合・期待Schema・effort low、effective providerを原paramsのまま検査する。
検証用確定ref `4376548a70987ffeb92da25f228b746224070024` の全572件はOK/exit0、関連104件を別文脈で同clean refに再実行（1.212秒、OK/exit0）。前後clean、3ファイルhash一致、阻害指摘なし。
期待Schemaは渡された値との一致までの検査である。原artifact許可集合・固定契約/manifest/入力の束縛、rollout/client/usage相関、独立採点Schema/有限実行器、親レシート/台帳確定はR02の残件。実provider・完全一次・Gate・Phaseは未認定。

## R02 原artifact・固定入力・共有予約の検分

[詳細記録](r02-artifact-review.md)に原指摘・是正・環境失敗・ref別検証を保存した。最終clean ref b64772aaで全591試験通過、別文脈でcanary44/ledger30試験通過、元3指摘の是正確認と追加阻害指摘0。原RPC/host/final/rollout/usageの相関、意味採点、親確定レシートは残る。一次・独立採点0、対象integrationブランチHEAD64aed6cc維持、pushなし。


## R02 原軌跡・校正・独立意味採点の接続

原RPC/host/native final・完全初期context・rollout/lastと累積usage、固定CLI50資源、局所校正04の原12artifactを照合する入口と、SOL独立意味採点の専用Schema/有限実行器/親レシート/共有台帳の確定を実装した。取得→構造→独立採点→親確定の入口は1attemptだけを進める。

元指摘と各是正refの結果はr02-native-review.json、r02-rollout-review.json、r02-runtime-calibration-review.json、r02-semantic-review.json、r02-durable-campaign-review.jsonに保持する。clean912c63faの全638試験と独立88canary/33ledgerは通過し、意味採点P2=2は是正確認されたが、他worker予約を誤停止するP2が追加された。新clean5bdfdb23で予約の所有通知・同ロック内番号検査を是正し、全件試験・独立検分中。

R02は検分待ち、R03は未着手。局所校正はnetwork隔離・認証mountなし・局所1要求・課金0であり、実provider/wire/送信前hard capを認定しない。一次/独立採点モデル0、integration HEAD64aed6cc維持、pushなし。R10ではREADME見出しをmanifest0.1.3へ整合し、その他の文書・継続評価は残る。

## 2026-10-12の続行

Schema送信投影と実Git集合重複を是正し、旧原失敗・停止を保持した。clean e026で全skills647件通過、別文脈の実入口とSchemaの是正確認済み。新日付の校正05は外部モデル0・局所1、原12artifactを固定しclean7a9fc8dへ接続。全skills648件と形式監査46ケース/7Schemaが通過した。校正05と新起動条件の独立検分は進行中で、新一次/独立起動は0。

R08原正式runは適合試験通過・単体2失敗。repo内TMPDIRの親設定混入を実Git境界で隔離し、clean5d86fc9の単体647件が通過した。新7a9fc8dの正式基準収集を実行中。異なる下限環境と同一最終refの集約は残り、Gate Cは未認定。R09は提案32へ候補・導入更新復旧ケース・証拠を保存し、実試験は後続。

## 2026-10-12 R03新条件初回

123c89固定のSE-001反復1は取得後の原構造照合で停止。新一次1・独立0、旧一次1停止とは別記録。/responses3件200、/models2件200、42原artifact hash保持。unknown tool telemetry fieldsを独立原因検分する。原usageは保存し認定usage/費用未確定、残3未起動、同条件retry0。詳細はr03-schema-projection-first-stopped.json。


### 2026-10-12 開発継続・新03準備

R05新02は準備SOL44の不正receipt型P2で一次0のまま停止。親が旧a697で5種類の型不正を実再現し、52421d33のdict検査と6型の恒久stop回帰へ是正した。全692試験72.746秒exit0/clean、関連19試験通過。旧01/02各準備1・一次0を保持し、新03の一次68・意味独立68・準備1・240秒・retry0を別source/output/ledgerへ固定した。独立preflight9.065秒exit0、開始前検分と有限1枠実行器の照合を進める。まだ新一次を測定していない。

R08は候補8fcdの元2環境各350適合・647単体と正式collectorを別文脈で検分し全4判定Passed、親でも独立記録70hashを再計算。認定は候補8fcdに限定する。2環境は同host/kernel/CPU上の実tmpfsとext4で、最終統合ref・Skill Gate・releaseは未認定。

R06は現候補の公開品質7ケースをa697で全5契約preflightし全exit0、モデル0。行動と収束の後続評価は残る。

詳細と原hashは r05-matrix-preparation-sol-02-stopped.json、r05-receipt-type-remediation.json、r08-gate-c-8fcd-independent.json、r06-public-quality-preparation.json を参照。

## 2026-10-13 R05の再開

旧06はSI010一次・意味検分・原照合通過後、SP001がREQ tests要素を文字列にしてCoreで拒否され停止。準備1/一次2/意味1を恒久保持した。sdd-plan0.1.2へ登録済みテストobject形式と見本を加え、新07はSP001を先頭にした独立した68一次/68意味/準備1の有限条件とした。

source915で全709試験74.546秒exit0/clean。13日の新cal06とsnapshot03の6skills72resourcesを原照合。独立検分で未使用一次driverの準備原混用P2を発見し、closed10/Git20/native/固定実行入力/予約の検査へ修正、親と独立の合成回帰を通した。実静的準備SOL49は37.490秒pass/指摘0、原10とGit20を親・独立の両方で照合した。SP001 skill反復1を単一開始した。まだ行動評価成功・全行列・Skill Gateを認定しない。

旧06の公開原52filesをevidence-r05-new06.tar.gzへ保存し、archive内bytesを原hashと確認。R06の行動評価前補修3対象をr06-premeasurement-hardening-queue.jsonへ保存。R04/R06/R07、最終統合refのR08、実ホストR09、R10文書・継続評価、R11の別系統/人間承認は残る。

2026-10-13: R05新07は一次17・意味16・親照合16で永久停止。SI-009のstop/handoff分類契約の曖昧さを独立確認。全68/Gate/releaseは未認定。原失敗・実消費は保持。次sourceで共通分類契約を明確にし、局所合成試験と独立検分後に別条件を準備する。

2026-10-13: R05新08はsourceea9772a0で静的SOL50を通過し、一次/別意味/親原照合が4/4/4通過。SI009はskill/baselineの両方でstop・open維持・人手待ち、SP001はREQ形式通過とTASK境界診断停止、SI010は既知障害を読取りCore/テスト未実行で停止した許可分岐。準備1件18.200371秒・全723回帰83.908秒。旧07失敗と実消費17/16/16は保持。R06開始前4件+版差替え1件はrefe05/独立101/全723で限定閉包、品質実モデル0。新08残64件・品質比較・後続Gate/releaseは未認定。計画正本とr05-new08-progress.jsonへ各開始/実消費/原hashを保存。


2026-10-13更新: R05新08は一次9件消費・8件完了、意味検分8件、親原照合8件。P09はprovider利用上限で中断し、原証拠を保持して新予約・モデル0で恒久停止を保存した。追加独立checkpointも利用上限で未完了。R05全体とリリースは未認定。


2026-10-13追加: 確定source `63b05dae22dce98e945c5fa7a09036b171481f7b` へR04の92枠台帳部品を実装・プッシュ。cleanで全740件とスキルaudit通過。原取得接続と独立検分は未実施。R06は公開7ケースpreflight通過（モデル0）、R09は現72資源の更新/旧71資源復元と不適合4種拒否をローカル確認。R05は利用上限による恒久停止を保持する。全体完成・Gate・リリースは未認定。
