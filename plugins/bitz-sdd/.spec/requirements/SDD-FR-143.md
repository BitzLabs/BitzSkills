---
id: SDD-FR-143
version: 1.0
status: verified
domain: workflow
priority: high
origin: SI-SDD-022, SI-SDD-023, SI-CORE-035
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-143 仕様遷移の認可・前提・永続化を一貫して保護する

- **説明**: 人間裁定必須遷移の保証範囲を明示的な対話入力までに限定し、要件とlocal taskの
  lifecycle前提を遷移前に検査する。受理した変更はworkspace単位の排他とwrite-ahead journalで
  artifactとSTATEへ回復可能に反映し、部分更新・偽の人間性表示・孤児要件を残さない。
  TTYは本人認証ではなく、provenanceは`interactive-confirmation-unverified`と記録する。
- **受入基準 (EARS)**:
  - WHEN 人間裁定必須遷移を要求した THEN `spec update` はstdinとstderrのTTYおよび対象ID・旧status・新statusの完全一致再入力を要求し、条件を満たさない場合は対象artifactとSTATEを変更せず`authorization-required`で終了すること SHALL
  - WHEN 対話確認を受理した THEN `spec update` はactorを1〜128 Unicode code pointかつ改行・ASCII制御文字なしに検証し、STATEの構造化eventへ`interactive-confirmation-unverified`として保存すること SHALL
  - WHEN 旧`--by-human`を指定した THEN `spec update` は互換aliasとして受理せず非ゼロ終了すること SHALL
  - WHEN requirementを`approved`から`implementing`へ遷移した THEN 所有workspace内に対象IDを`implements`するtaskが1件以上無ければ両ファイルを変更せず`precondition-failed`で終了すること SHALL
  - WHEN requirementを`implementing`から`verified`へ遷移した THEN 所有workspace内の対象taskが1件以上かつ全件`done`でなければ両ファイルを変更せず未完了taskを診断すること SHALL
  - WHEN updateまたはscaffoldがworkspaceを変更した THEN 共通mutation lockは同一workspaceの対応writerを直列化し、競合時は既存内容を変更せず`mutation-conflict`で終了すること SHALL
  - WHEN artifactとSTATEを更新した THEN journalはschema version・event ID・SHA-256 before/after hash・完全after payload・PREPARED/APPLIED/COMMITTED phaseを保持し、成功応答前に両対象とdirectoryをdurableに永続化すること SHALL
  - WHEN mutationが任意の書込み境界で中断した THEN 次回mutationまたはinspectは未完了transactionを検出し、hashで一意に判定できる場合だけ`--recover`または`--recover-lock`で完了・清掃すること SHALL
  - WHEN STATEへ機械eventを保存した THEN canonical JSONをRFC 4648標準Base64でHTML commentへ格納し、inspectはschema・event ID一意性・表示行との対応・遷移連鎖を検査すること SHALL
- **検証手段**: `tests/test_spec_transaction.py`、`tests/test_spec_update.py`、
  `tests/test_spec_inspect.py`で認可、local task前提、競合、各phaseの障害注入、復旧、
  structured event破損をunit-testする。共有スクリプト変更のため全pytestとrelease checkを実行する。
- **Revision History**:
  - 1.0 (2026-07-27) 初版（draft起票）。SDD-DSN-005、SI-SDD-022/023、SI-CORE-035から導出。
