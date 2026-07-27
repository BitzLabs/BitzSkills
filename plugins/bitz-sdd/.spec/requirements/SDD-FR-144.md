---
id: SDD-FR-144
version: 1.0
status: verified
domain: workflow
priority: medium
origin: SI-SDD-024, SI-CORE-035
verification_method: unit-test
derived_from:
supersedes: CORE-FR-004
superseded_by:
confidence: high
---

### SDD-FR-144 並行環境で仕様IDの生成と統合を安全側に制御する

- **説明**: 同一worktreeのTOCTOUをworkspace lockと排他的公開で防ぎ、cross-branchでは
  Plan直列化とtarget commit SHAへ束縛したintegration preflightで衝突をmerge前に検出する。
  中央採番サービスは導入せず、検出不能な環境では安全側に停止する。
- **受入基準 (EARS)**:
  - WHEN `spec scaffold`が番号を自動採番した THEN workspace lock取得後に既存最大番号を再走査し候補を決定すること SHALL
  - WHEN scaffold候補pathを公開した THEN 完全なUTF-8 payloadをfsyncした一時ファイルからatomic no-replaceで公開し、既存pathを上書きしないこと SHALL
  - WHEN scaffoldが公開境界で中断した THEN journalとdestination hashから未公開・公開済み・曖昧の3分類で復旧し、部分ファイルを正式pathへ残さないこと SHALL
  - WHEN scaffold候補が別processに先行生成された THEN 自動で別番号へ進まず非ゼロ終了し、呼出者へ再実行を要求すること SHALL
  - WHEN integration preflightへtarget refを指定した THEN inspectは解決したtarget commit SHAを出力し、target側のIDとの重複・target非包含base・accepted issue由来成果物の消失を検出すること SHALL
  - WHEN merge直前のtarget SHAがpreflight記録と異なる THEN required checkまたはmerge queueは判定を失効させ再検査を要求すること SHALL
  - WHEN target SHAを証明できない環境でcross-branch統合を要求した THEN integration preflightはfail-closedで終了すること SHALL
  - WHEN accepted issueから正式IDを採番した THEN coordinatorは採番commitを統合してから共通baseとして実装worktreeを分岐し、実装中の並列workerは正式IDを採番しないこと SHALL
- **検証手段**: `tests/test_spec_scaffold.py`と`tests/test_spec_inspect.py`で2process競合、
  排他的公開、障害復旧、target ref更新・重複・非包含baseをunit-testする。
  lifecycleとsdd-gitの運用契約をrelease checkおよび目視で確認し、全pytestを実行する。
- **Revision History**:
  - 1.0 (2026-07-27) 初版（draft起票）。SDD-DSN-005、SI-SDD-024、SI-CORE-035から導出。
