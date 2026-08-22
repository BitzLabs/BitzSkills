---
id: FLW-NFR-014
version: 2.2
status: implementing
domain: safety
priority: high
origin: SI-FLW-078, SI-FLW-079, SI-FLW-081
verification_method: unit-test
derived_from: FLW-FR-006, FLW-NFR-007, FLW-NFR-012, FLW-NFR-013
supersedes: FLW-NFR-013
superseded_by:
confidence: high
---

### FLW-NFR-014 M2 Local Safety Profileの再照合・競合排除・耐久証跡

- **説明**: M2のwrite safetyを、同一OSユーザーが管理するローカルfilesystem上の複数process競合と
  通常運用上のcrash・破損へ限定する。承認はplan-digestへ統一し、process間lease、mutation直前再照合、
  原子的なcontract bundle有効化、追記型証跡で安全側へ停止する。
- **受入基準 (EARS)**:
  - WHEN M2のOperationPlanを作成する THEN bitz-flowはcontract version、repository identity、target、
    HEAD/index/worktree snapshot、期限、単回nonceを正規化した`operation_id`へ固定すること SHALL
  - WHEN M2のapplyを要求する THEN bitz-flowは`--confirm <operation_id>`、未使用nonce、有効期限を検査し、
    不一致、期限切れ、再利用をGit副作用0件で`BLOCKED`または`STALE`にすること SHALL
  - WHEN M2で`signed-capability`の宣言、capability fileまたはtrusted key registry依存の入力を検出する THEN
    bitz-flowは無言で`plan-digest`へ降格せず、内部reasonを`UNSUPPORTED_APPROVAL_MODE`、公開resultを
    `code: UNSUPPORTED`かつ`cause: unsupported-approval-mode`として返すこと SHALL
  - WHEN repository、GitまたはOS由来pathをguard key、operation identityまたはtarget scopeへ固定する THEN
    bitz-flowはnative componentを可逆なplatform別表現で保持し、case-insensitive volumeでは別のcollision keyを
    導出し、安全に導出できない不在targetを`UNSUPPORTED`にすること SHALL
  - WHEN同一canonical targetへ複数processがwriteをapplyする THEN bitz-flowはGit起動権限を持たない
    単一ローカルauthorityを通じてOS lock、単調fencing token、operation journalを更新し、各mutation直前に
    lock保持、最新token、plan snapshotを再照合して最大1processだけをmutationへ進めること SHALL
  - WHEN最初のGit mutationへ進む THEN bitz-flowは同一filesystemへoperation intentと有効な
    `INDETERMINATE`緊急receiptを先にdurable公開してnonceを消費済みにし、公開できなければ
    Git副作用0件で停止すること SHALL
  - WHEN 正常terminal receiptが緊急receiptを置き換える THEN bitz-flowは同一operation chain上で
    `supersedes_receipt_digest`を記録し、複数後継、branchまたはchain外参照を`INDETERMINATE`にすること SHALL
  - WHEN operation phaseを永続化する THEN bitz-flowは`LOCKED`、`INTENT_DURABLE`、`MUTATING`、
    `RESULT_DURABLE`、`DONE`または`QUARANTINED`の順序、単調sequence、直前digestを守り、gap、branch、
    改変、未知event、postcondition不確定を`INDETERMINATE`として後続mutationを停止すること SHALL
  - WHEN contract v2 schemaを有効化する THEN bitz-flowはschema、codec、runtime version、member一覧を持つ
    単一bundle manifestをowner-only stagingへ生成・検証し、exclusive local promotion lock下で
    all-or-nothingにcurrent pointerへatomic publishすること SHALL
  - WHEN promotion中にbundle、runtime identityまたはcurrent generationが変化する THEN bitz-flowは
    active公開前の最終再照合で`STALE`にし、部分active stateを残さないこと SHALL
  - WHEN 通常applyまたはpromotionを開始する THEN bitz-flowは同じlocal promotion lock下でactive operation
    markerを登録・照合し、active markerがあるpromotionとpromotion中の新規applyを相互排他にすること SHALL
  - WHEN promotion lockとtarget lockを使用する THEN bitz-flowは両者を同時保持せず、promotion marker操作後に
    promotion lockを解放してからtarget lockを取得し、lock timeoutをGit副作用0件の`BLOCKED_LOCK_BUSY`にすること SHALL
  - WHEN platform adapterがlocal filesystemのowner、非追随path walk、file identity、OS lock、
    file/directory durabilityを安全に観測できない、またはnetwork/unknown filesystemを検出する THEN
    bitz-flowは`UNSUPPORTED_FILESYSTEM`を返し、自己診断だけでsupportedへ格上げしないこと SHALL
  - WHEN operationがcrashまたはpostcondition不確定で停止する THEN bitz-flowはworktreeと証跡を保持し、
    自動解除・自動削除・自動再実行を行わず、read-only auditと明示確認付きreconcileだけを案内すること SHALL
  - WHEN 明示確認付きreconcileが確定済みGit状態と最長有効journal prefixを照合する THEN bitz-flowは
    単一authority経由で冪等なclosure eventだけを追記し、Git mutationを起動せず、新しい操作には新planを要求すること SHALL
  - WHEN plan、auditまたはreconcileがrepository stateを観測する THEN bitz-flowはallowlist済みread-only Git commandだけを
    起動できる`RepositoryObserver`からmachine-readable snapshotを取得し、write-capable optionまたは未知commandを
    Git副作用0件で拒否すること SHALL
  - WHEN 運用者がdoctor、auditまたはverify-receiptを実行する THEN bitz-flowは永続stateを変更せず、
    result code、cause code、side-effect state、自動復旧可否、次のoperator action、operation ID、receipt参照、
    journal使用量をclosed JSONで返すこと SHALL
  - WHEN M2のjournalまたはreceiptを管理する THEN bitz-flowはarchive、prune、restore、自動削除を行わず、
    owner-onlyのローカル原本を保持すること SHALL
  - WHEN M2の公開可否を検証する THEN bitz-flowは適用可能な全crash injectionで有効なreceipt chain 100%、
    同一targetのwrite-capable Git child最大1、pre-mutation拒否時のGit副作用0件、部分active bundle 0件、
    read-only commandの永続write 0件、reconcile重複closure 0件を満たすこと SHALL
  - WHEN registered local profileのreference fixtureでdoctor、auditまたはverify-receiptを実行する THEN
    bitz-flowはjournal 10,000 event以下かつreceipt合計100 MiB以下の条件で、child timeoutを含め30秒以内に
    closed terminal resultを返し、時間超過も例外やhangではなくclosed timeout resultにすること SHALL
- **検証手段**: unit testと複数process fault fixtureで、plan-digest正常系、signed-capability拒否、
  native path/case collision、lock競合、全crash point、counter破損、journal gap/branch/改変、緊急receipt、
  bundle promotion競合、network filesystem拒否、read-only commandの非変更、reconcile冪等性を検証する。
  Linux・macOS・Windowsの登録済みlocal filesystem fixtureで通常系`UNSUPPORTED` 0件を出口条件とする。
- **Revision History**:
  - 2.2 (2026-08-22) `UNSUPPORTED_APPROVAL_MODE`を内部reasonとし、公開resultを
    `UNSUPPORTED` / `unsupported-approval-mode`へ一意に写像
  - 2.1 (2026-08-22) read-only Git観測境界と、運用受入マトリクスに対応する定量的な公開条件を追加
  - 2.0 (2026-08-22) M2 Local Safety Profileへ縮退し、署名policy、archive、RBAC、通知/RTOを除外。
    単一authority、緊急receipt、bundle単位promotion、手動reconcileへ契約を再構成
  - 1.3 (2026-08-22) Safety Kernel/Control Plane分離、不変journal、運用API、key lifecycle、support/retention、段階展開を追加
  - 1.2 (2026-08-22) native path非衝突、trusted promotion線形化、quarantine裁定記録を追加
  - 1.1 (2026-08-22) 旧runtimeの保証境界をsentinel-aware baselineへ限定しpromotion barrierを追加
  - 1.0 (2026-08-22) `FLW-REV-021`と`SI-FLW-078/079`を受けた後継契約案をdraft起票
