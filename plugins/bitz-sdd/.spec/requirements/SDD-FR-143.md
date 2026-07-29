---
id: SDD-FR-143
version: 2.1
status: verified
domain: workflow
priority: high
origin: SI-SDD-022, SI-SDD-023, SI-CORE-035, SI-SDD-026
verification_method: unit-test
derived_from:
supersedes: CORE-FR-005
superseded_by:
confidence: high
---

### SDD-FR-143 仕様遷移の認可・前提・永続化を一貫して保護する

- **説明**: 対話確認経路の保証範囲を明示的な対話入力までに限定し、要件とlocal taskの
  lifecycle前提を遷移前に検査する。受理した変更はworkspace単位の排他とwrite-ahead journalで
  artifactとSTATEへ回復可能に反映し、部分更新・偽の人間性表示・孤児要件を残さない。
  TTYは本人認証ではなく、provenanceは`interactive-confirmation-unverified`と記録する。
  人間裁定必須遷移の認可経路全体（対話確認・代行可視化の2経路と経路の排他）の規定は
  SDD-FR-145 が正であり、本要件のTTY節は対話確認経路を指定した要求に適用される。
- **受入基準 (EARS)**:
  - WHEN 対話確認経路（`--interactive-decision`）で人間裁定必須遷移を要求した THEN `spec update` はstdinとstderrのTTYおよび対象ID・旧status・新statusの完全一致再入力を要求し、条件を満たさない場合は対象artifactとSTATEを変更せず`authorization-required`で終了すること SHALL
  - WHEN 対話確認を受理した THEN `spec update` はactorを1〜128 Unicode code pointかつ改行・ASCII制御文字なしに検証し、STATEの構造化eventへ`interactive-confirmation-unverified`として保存すること SHALL
  - WHEN 旧`--by-human`を指定した THEN `spec update` は互換aliasとして受理せず非ゼロ終了すること SHALL
  - WHEN requirementを`approved`から`implementing`へ遷移した THEN 所有workspace内に対象IDを`implements`するtaskが1件以上無ければ両ファイルを変更せず`precondition-failed`で終了すること SHALL
  - WHEN requirementを`implementing`から`verified`へ遷移した THEN 所有workspace内の対象taskが1件以上かつ全件`done`でなければ両ファイルを変更せず未完了taskを診断すること SHALL
  - WHEN updateまたはscaffoldがworkspaceを変更した THEN 共通mutation lockは同一workspaceの対応writerを直列化し、競合時は既存内容を変更せず`mutation-conflict`で終了すること SHALL
  - WHEN artifactとSTATEを更新した THEN journalはschema version・event ID・SHA-256 before/after hash・完全after payload・PREPARED/APPLIED/COMMITTED phaseを保持し、成功応答前に両対象とdirectoryをdurableに永続化すること SHALL
  - WHEN mutationが任意の書込み境界で中断した THEN 次回mutationまたはinspectは未完了transactionを検出し、hashで一意に判定できる場合だけ`--recover`または`--recover-lock`で完了・清掃すること SHALL
  - WHEN STATEへ機械eventを保存した THEN canonical JSONをRFC 4648標準Base64でHTML commentへ格納し、inspectはschema・event ID一意性・表示行との対応・遷移連鎖を検査すること SHALL
  - WHEN workspaceの`.spec/PROJECT.md`が`audit_baseline`を宣言していない THEN inspectはbaseline監査を実行せずgitを一切呼び出さないこと SHALL
  - WHEN `audit_baseline`を宣言したworkspaceでbaseline時点のstatusと記録済みeventの始点が食い違い、その未記録の到達状態が人間裁定必須状態（`approved`/`promoted`/`deprecated`/`accepted`/`rejected`/`superseded`）である THEN inspectは`audit-corruption`として非ゼロ終了すること SHALL
  - WHEN `audit_baseline`を宣言したworkspaceでbaseline commitをgitから解決できない THEN inspectは監査未実行をWARNとして報告しFAILさせないこと SHALL
- **検証手段**: `tests/test_spec_transaction.py`、`tests/test_spec_update.py`、
  `tests/test_spec_inspect.py`で認可、local task前提、競合、各phaseの障害注入、復旧、
  structured event破損、baseline監査（未宣言時の無検査・未記録到達状態の検出・git解決失敗時のWARN）を
  unit-testする。共有スクリプト変更のため全pytestとrelease checkを実行する。
- **Revision History**:
  - 2.1 (2026-07-29) CLI迂回（`spec update`を通さないstatus手編集）の事後検出をbaseline監査として追加
    （SI-SDD-026）。既存9節の意味は不変で、eventを持つartifactの検査挙動も変えないため既存unit-testは
    全件greenのまま。追加3節は`audit_baseline`宣言時のみ作動するオプトイン契約。
  - 2.0 (2026-07-27) TTY節の適用範囲を対話確認経路の指定時に限定（SI-SDD-027 / SDD-FR-145）。
    保証内容は不変で、限定により除外される代行可視化経路の契約は SDD-FR-145 が引き受ける。
    既存unit-testは全件greenのまま（対話確認経路の挙動変更なし）。
  - 1.0 (2026-07-27) 初版（draft起票）。SDD-DSN-005、SI-SDD-022/023、SI-CORE-035から導出。
