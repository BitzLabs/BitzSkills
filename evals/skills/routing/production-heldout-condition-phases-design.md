# 保持評価の条件phase継続（設計候補）

対象は固定purpose heldout-matrix-survey-remaining23-20261024-01。製品72/ケース12×2/期待/指示/catalog/protocol/schema/SDK/runtimeは固定。旧停止1・一次消費1/pending1と完了2正解・一次/独立消費各2を保持する。次はordinal4..24、追加21枠。REQ/TECHの意味、Gate、製品を変更しない。

## 不変条件と形式

- 当日校正、source/input/現物全照合、独立具体prelaunch、retry0、最大2、private owner-only EXCLを維持。
- 新execution v0.2は既存fieldsにconditionPhaseだけ追加。purpose anchor SHA、phase index、前activation SHA、前journal head SHA、開始ordinalを固定。旧v0.1の分岐は変更しない。
- genesis anchor（公開安全metadataのみ）へsource559/ledger238cd569/execution2a4b2a1d/inputca4ecf95/proof4c987402/headad971f71/14events/旧stop15660dd2/不変入力hashを一度固定する。
- registry rootは固定 measurement-ledgers/r04-heldout-condition-phases-01。phase連番/ledger rootは形式から解決し、日付ごとのコード定数を増やさない。上限64phase、各原/総bytesも有限。新ref/rootにより予算を返却しない。
- 各phase内はimmutable legacy型base ledger contract（当該source/input/resourceproof）と追記event。現在のphaseと全先行phaseから消費/終端を再計算し、利用者のcarry数値は信用しない。全purposeでprimary<=24、independent<=24、正常終端+旧停止<=24。global_stopがある新phaseは移行不可。

## 管理sealと取引

1. current-day資源と正prelaunch成立後、共通campaign batch lock、purpose lock、前phase ledger lockの順で排他する。
2. 完全terminal境界（pending新0）または空phase（予約/started/event0、carry不変）だけを許す。captured/予約/started/未知/不整合/global_stopは拒否。
3. 前head/契約/全先行原を再照合。前rootへ固定名condition-seal.jsonをEXCL新規保存。既契約/14event/完了原は不変。旧readerはunknown inventoryで拒否し、旧入口から追加予約できない。sealをglobal_stopや評価失敗に変換しない。
4. 独立reviewを束縛したsealと前registry headからactivationをEXCL保存。新phase rootを初期化後だけ予約する。
5. seal後activation前に中断した状態ではpaid不可。同じ元proposal/review/next条件に完全一致する管理処理の完了だけを許し、sealの上書き/削除/別条件への差替えをしない。
6. 新readerはregistry/proposalに一致した固定seal名だけを歴史readerで認識する。一般的unknown file/schema許容を追加しない。旧phaseと全歴史原も毎回照合。

## hashのDAGとadmission

execution phaseheader（前activationのみ）→proposal（前head/再計算carry/新execution/deployment/input/resourceproof）→独立report/review（proposal SHAとcondition）→seal（proposal/review）→activation（proposal/seal/review/前head）。相互hash参照は禁止。

BoundExecution.ledger_contractのphase分岐だけはreview/report/isolationも要求し、factoryへmetadata admission envelopeを渡す。全caller(run/operator/score)で同じ検分原を供給する。準備用proposal関数はreadonlyであり単独で起動を許さない。旧分岐のAPIとraw bytesは維持。

実接続用headerは`heldout-condition-phase-header-0.2.0`とし、`priorLaunch`に最後の完了起動のphase番号・ordinal・role・旧execution SHA・旧source・receipt SHA・pacing SHA・wall時刻を固定する。空phaseを飛ばした実原から派生し、proposalより前に確定するためhash循環を作らない。workerでもこのmetadataとphase先頭pacingを厳密照合する。未接続のv0.1 prototypeの通過を新形式の起動許可へ読み替えない。

`production_heldout_phase_registry.py`のproposal/admission builderは公開metadataと検査済みsnapshotを引数に取り、自己申告carryを採用せず全条件を再構成する。review/report/isolationは空白・改行を含む原bytesを保持する。registry readerと管理seal/activation、全caller接続が完成するまで、新execution v0.2の`ledger_contract`は明示拒否する。

## 時計・日付

- 歴史receipt/control/pacingは各旧executionで検証。当日要求は新launch資源へ適用し、歴史へ遡及しない。
- phase最初の一次は空phaseを飛ばし最後の完了started receipt/controlを照合。新時計で完了witness後必ず60秒待ち、前原/registryを再照合してv0.3 handoff pacingをEXCL保存。旧monoを現monoから減算しない。wall逆行・fake sleep・降格を拒否。
- 新phase内の後続は従来の現時計chain。phase最初のpacingはexecutionのphaseheaderと前完了原hashへ束縛し、child側では公開metadataだけで形式検証する。
- 実行中の当日要求も維持。新予約前にtimeout/gap/検査余裕に必要な残日時間を確認し、日付境界直前の新batchを見合わせる。途中状態を別phaseへ付け替えない。

## 検証と採用

- 合成試験: carry算術・23/24分母・failures/旧pending・旧seal拒否・immutable全原・契約/head drift・偽carry・二重activation/concurrent lock・crash管理回復・全phase上限・空phase/clock reset/60秒/降格/旧条件解決・残日時間・legacy rawの退行。
- 実原は必要なmetadataだけreadonly照合。ケース/期待/認証本文/opaqueを表示・公開しない。
- 確定source全回帰、独立code検分、Date26校正と両role隔離/固定catalog診断、source-bound proposalの具体独立prelaunchと親全原照合後だけseal/activation/ordinal4を開始する。
