---
id: FLW-NFR-014
version: 1.2
status: implementing
domain: safety
priority: high
origin: SI-FLW-078, SI-FLW-079
verification_method: unit-test
derived_from: FLW-FR-006, FLW-NFR-007, FLW-NFR-012, FLW-NFR-013
supersedes: FLW-NFR-013
superseded_by:
confidence: high
---

### FLW-NFR-014 approval-mode 宣言の観測可能な再照合と安全な束縛

- **説明**: 配備意図を示す `approval-mode.json` をreview済みGit blobとOS file identityへ
  束縛し、plan・承認・各mutationの観測点で承認強度の変化をfail-closedに停止する。
- **受入基準 (EARS)**:
  - WHEN bitz-flowが`approval-mode.json`を評価する THEN repository rootから各path componentを
    symlink/reparse-point非追随で検査し、HEAD・index・worktreeの三者すべてに宣言が無い場合だけを
    `absent`とし、宣言が存在する場合はregular file、実行processの有効OS principal所有、
    group/world非書込み、HEAD追跡済み、HEAD・index・worktreeのblob一致をすべて満たす宣言だけを
    `bound`とし、HEAD/indexにblobがあるworktree削除・staged deletionを含むその他を`invalid`として
    `BLOCKED`にすること SHALL
  - WHEN `bound`または`absent`の宣言からOperationPlanを作成する THEN bitz-flowはcontract version、
    repository identity、宣言状態、mode、HEAD tree/blob、content digest、file identityを正規化した
    `approval_declaration_digest`をsnapshotとoperation identityへ固定すること SHALL
  - WHEN repository、GitまたはOS由来pathをguard key、nonexistence digest、operation identityまたは
    capability scopeへ固定する THEN bitz-flowはnative componentを可逆なplatform別表現で保持し、Unicode
    normalizationで別directory entryを同一scopeへ畳み込まず、不在targetをparent directory identityと
    末尾native componentへ束縛すること SHALL
  - WHEN signed-capabilityを検証する THEN bitz-flowはcontract version 2と
    `approval_declaration_digest`を署名対象の必須fieldとし、旧version、field欠落、未知fieldまたは
    plan contextとの不一致を`BLOCKED`にすること SHALL
  - WHEN applyの承認検証後かつ永続target lease取得後、または各Git mutation起動直前に宣言を
    再評価する THEN bitz-flowはplan時と観測状態またはdigestが異なる場合を`STALE`または`BLOCKED`とし、
    当該再照合点以後のGit副作用を0件にし、成功した最終再照合を承認判定の線形化点として
    resultとreceiptへ記録すること SHALL
  - WHEN plan時と全必須再照合点で宣言が`absent`である THEN bitz-flowは既存の`plan-digest`承認を
    利用でき、必須観測点の間に発生して同じ`absent`へ戻った一時変化を検出済みとは報告しないこと SHALL
  - WHEN同一canonical targetへ複数processがwriteをapplyする THEN bitz-flowはcommon-dirのOS lockと
    単調増加fencing tokenを用い、各mutation直前にlock保持と最新tokenを再照合して最大1processだけを
    mutationへ進め、Git child終了までleaseを継承または監督し、取得不能または復旧不能なら
    副作用なしで`BLOCKED`または`UNSUPPORTED`を返すこと SHALL
  - WHEN宣言の再照合結果を返すまたはreceiptへ記録する THEN bitz-flowは秘密本文を含めず、
    contract version、状態、digest、再照合phase、result code、原因分類、fencing tokenを記録すること SHALL
  - WHEN platformでowner principal、非追随path walk、OS lockまたはfile identityを安全に検証できない THEN
    bitz-flowは`bound`を成立させず`UNSUPPORTED`または`BLOCKED`を返すこと SHALL
  - WHEN fencing stateを更新する THEN bitz-flowは`LOCKED`、`TOKEN_DURABLE`、`INTENTION_DURABLE`、
    `MUTATING`、`POSTCONDITION_DURABLE`の順序とfile/directory durabilityを守り、欠損、巻戻り、overflow、
    未知状態またはpostcondition不確定を`INDETERMINATE`として後続mutationを停止すること SHALL
  - WHEN contract v2 stateの有効化を要求する THEN bitz-flowのpromotion preflightは、サポート対象の
    launcher・CLI・plugin cacheを含む全起動経路がminimum-runtime sentinelを検査するbaseline以降であり、
    pre-baselineの起動経路が無効化されていることをinventoryと実行fixtureで証明し、証明できない環境では
    v2 state生成を`UNSUPPORTED`または`BLOCKED`にすること SHALL
  - WHEN promotion preflightがentrypointを検証する THEN bitz-flowは配布側のversioned baseline manifestを
    信頼根とし、親processが保持handleからartifactを測定して一致した実体だけを制限付きprobeで実行し、
    contract v2 stateのdurability commit直前にregistry generation、file identity、artifact digestを再照合して、
    差異・timeout・終了不能・出力超過・副作用を安全側へ停止すること SHALL
  - WHEN sentinel-aware baselineのpromotionが完了した環境でruntimeまたはschema versionを切り替える THEN
    bitz-flowはminimum runtime versionをcontract v2 stateより先に永続化し、sentinelに未対応のversionの
    起動とv2 pending stateを無視したrollbackを`BLOCKED`にすること SHALL
  - WHEN reviewerがquarantine解除を裁定済みとして記録する THEN bitz-flowは通常operationとGit mutationを
    開始せず、role付きreviewer署名と単回nonceを検証し、同一targetのOS lock下で最新chain head、fencing token、
    postconditionを再照合してdurable release receiptだけを追記し、成功後も新しいplanと通常承認を要求すること SHALL
- **検証手段**: unit testと複数process fault fixtureで、HEAD固定の正常系、absentのplan-digest、
  path component symlink/reparse point、staged-only・未追跡・権限不正、各再照合点の差替え、旧capability、
  NFC/NFD native path衝突、lock競合・parent/child process crash・counter破損、2^53超token、
  sentinel-aware旧runtime起動、baseline不一致、probe timeout、registry差替え、並行quarantine解除を検証し、
  pre-baseline起動経路が残るpromotionと不確定な解除を拒否して、停止判定後のGit副作用0件と
  receiptの原因追跡を確認する。Linux・macOS・Windowsの必須fixtureで通常系`UNSUPPORTED` 0件を出口条件とする。
- **Revision History**:
  - 1.2 (2026-08-22) native path非衝突、trusted promotion線形化、quarantine裁定記録を追加
  - 1.1 (2026-08-22) 旧runtimeの保証境界をsentinel-aware baselineへ限定しpromotion barrierを追加
  - 1.0 (2026-08-22) `FLW-REV-021`と`SI-FLW-078/079`を受けた後継契約案をdraft起票
