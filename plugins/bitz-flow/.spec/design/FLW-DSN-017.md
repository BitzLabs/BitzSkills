---
id: FLW-DSN-017
title: "M2 Local Safety Profileの競合排除・耐久証跡・原子的promotion"
status: draft
version: 2.2
updated: 2026-08-22
owner: codex
implements: FLW-NFR-014
origin: SI-FLW-077, SI-FLW-078, SI-FLW-079, SI-FLW-080, SI-FLW-081, SI-FLW-082
---

# FLW-DSN-017 M2 Local Safety Profileの競合排除・耐久証跡・原子的promotion

## 背景 / 課題

`FLW-REV-024`は、v1.5がローカルCLIの安全制御を越えて、署名policy、reviewer key lifecycle、
archive/restore、RBAC、通知、RTOを備える運用control planeへ拡大した結果、設計境界を閉じられず
`FAIL`になったと判定した。

2026-08-22の人間裁定により、M2は**Local Safety Profile**へ縮退する。目的は、複数AIエージェントや
processが同じrepositoryを操作する通常運用で、stale plan、競合write、crash、部分成功を安全側へ止め、
人間が短い証跡から再開判断できるようにすることである。悪意ある同一OSユーザーへの改ざん耐性や
長期監査基盤は目的に含めない。

## 1. スコープと信頼境界

### 1.1 保証すること

- 同じcanonical targetに対する複数local processの同時writeを直列化する。
- plan後のHEAD、index、worktree、target identityの変化をmutation直前に検出する。
- Git副作用の前に、crash後も残るintentと安全側の緊急receiptを確定する。
- 完了を証明できない操作を`INDETERMINATE`または`QUARANTINED`として保持する。
- contract v2を部分activeにせず、単一bundleとして原子的に有効化する。
- Linux、macOS、Windowsの登録済みlocal filesystem adapterで同じlogical resultへ収束する。

### 1.2 信頼するもの

- repositoryとGit common-dirを管理する同一OSユーザー。
- owner-only、非symlink/reparse-pointのlocal filesystem namespace。
- bitz-flow配布物に同梱されたcontract bundle member一覧とplatform allowlist。
- Gitのmachine-readable出力と、各副作用直後に再取得したrepository state。

### 1.3 M2で保証しないこと

- 同一OSユーザー、root、malwareがreceipt、runtime、registryを整合的に改ざんする攻撃。
- network filesystem、remote filesystem lock、cross-host lease、remote write。
- `signed-capability`、reviewer key registry、root of trust、key rotation/revocation。
- journal/receiptのarchive、prune、restore、自動削除、長期監査保存。
- 運用RBAC、通知adapter、pager、RTO/SLO。
- `worktree.finish`、`worktree.discard`、remote branch削除。これらはM3まで`UNSUPPORTED`とする。

### 1.4 用語表

| 用語 | 定義 | 生成・更新主体 | 寿命 / 終了条件 |
|---|---|---|---|
| `plan-digest` | closed approval contextのcanonical digest。CLIではこのdigestから導出した`operation_id`を確認値として使う | `ApprovalContext` | plan生成から`expires_at`、nonce消費、またはcontext変化まで |
| `operation_id` | operation、repository、target、snapshot、effects、期限、nonceを束縛する操作識別子 | `ApprovalContext` | operation chainの全event・receipt・operator actionで不変 |
| `nonce` | planの単回性を保証する値 | `ApprovalContext`が発行し、`TargetTransaction`が消費を確定 | `INTENT_DURABLE`公開時に消費済み。再利用不可 |
| `collision_key` | 同じ資源への競合を直列化するcase-aware target identity | `PlatformAdapter` | parent/resource identityまたはcase semanticsが変わるまで |
| `lease context` | OS lock、fencing token、operation IDを束縛したmutation権限 | `TargetTransaction` | target lock解放または監督対象childの終了証明まで |
| `intent event` | planned effectsとpreconditionを副作用前に固定する`INTENT_DURABLE` event | `TargetTransaction` | 削除しない。terminal/closure後もchain原本として保持 |
| `emergency receipt` | mutationが起きた可能性を副作用前から表す`INDETERMINATE` receipt | `TargetTransaction` | 削除せず、単一の後続terminal receiptにだけsupersedeされる |
| `terminal receipt` | `DONE`または`QUARANTINED`の最終判断とpostconditionを持つreceipt | `TargetTransaction` | 同一operationの最長有効chainにある最後の1件を正とする |
| `closure event` | 人間判断済みreconcileを記録する、Git mutationを伴わない冪等event | `TargetTransaction` | 同一decision digestでは1件。異なる判断は新audit/planが必要 |
| `active operation marker` | promotionと通常applyの同時進行を防ぐdurable marker | `PromotionBarrier` | terminal receipt確定後に解除。crash時はreconcileでclosure証明後に解除 |
| `current pointer` | activeなcontract bundle generationとdigestを指すowner-only regular JSON | `PromotionController` | 次の成功promotionによるatomic replaceまで |

本文、schema、result、runbookはこの用語を正とし、`approval token`、`lease receipt`、`active manifest`などの
別名を導入しない。OS固有名は`PlatformAdapter`内部に閉じ、公開resultでは上表のlogical nameへ正規化する。

## 2. 承認契約をplan-digestへ統一する

M2の承認contextは次のclosed fieldから`operation_id`を導出する。

```text
contract_version       # 2
operation
repository_identity
target_collision_key
head_oid
index_digest
worktree_digest
planned_effects
expires_at
nonce
```

planは副作用なしで`operation_id`、`expires_at`、単回`nonce`、確認文を返す。applyは
`--confirm <operation_id>`を要求し、nonce未使用・期限内・再導出context一致を検査する。
各Git child起動直前にも同じcontextを再照合し、差異は`STALE`、観測不能は`BLOCKED`または
`UNSUPPORTED`とし、その時点以後のGit副作用を0件にする。

HEAD、index、worktreeのいずれかに`approval-mode.json`が存在する、またはCLIに
`--capability-file`やtrusted key registry依存の入力がある場合は、内容を承認へ使わず
内部reason `UNSUPPORTED_APPROVAL_MODE`で停止する。公開resultでは既存の大分類
`code: UNSUPPORTED`とclosed cause `unsupported-approval-mode`へ一意に写像し、内部reasonを
result codeへ直接追加しない。`plan-digest`へ無言降格しない。存在確認はrepository rootから
component単位の非追随walkで行い、staged-only、worktree-only、削除途中も「存在する可能性あり」として停止する。
これにより過去B2配備の意図を誤って弱めず、M2実装から暗号鍵管理を除去する。

## 3. target identityとplatform境界

### 3.1 表示identityと競合identityを分離する

- `display_path`: native componentを可逆に表現し、人間への表示とreceiptへ使う。
- `collision_key`: parent directoryのcase semanticsとresource identityから導出し、lock keyへ使う。
- 不在targetはparent directory identityと末尾native componentへ束縛する。
- case-insensitiveかどうかを安全に判定できない不在targetは`UNSUPPORTED_FILESYSTEM`とする。
- Unicode normalizationで別directory entryを同一scopeへ畳み込まない。

### 3.2 platform adapter

platform adapterはpolicyを決めず、owner、ACL/mode、非追随walk、regular file/directory identity、
case semantics、OS lock、file/directory durability、child process監督のclosed evidenceだけを返す。

サポート対象はコード同梱の静的allowlistと起動時semantic self-testの両方で決める。self-testだけで
未知filesystemをsupportedへ格上げしない。network filesystem、owner取得不能、lock semantics不明、
directory fsync相当を確認できない環境は理由付き`UNSUPPORTED_FILESYSTEM`とする。
support profileへの署名や外部更新機構は持たない。

## 4. 単一のTargetTransaction authority

`TargetTransaction`はGitを起動できないローカルmoduleであり、次の更新を行う唯一のauthorityとする。

- canonical targetのOS lock取得・解放
- uint64 decimal stringの単調fencing token発行
- operation intent、phase event、terminal receiptの追記
- journal chainの最長有効prefix照合
- reconcile closure eventの冪等追記

`MutationCoordinator`は`TargetTransaction`が発行したlease contextを使って**write-capable Git child**を
起動できる唯一のcomponentとする。`RepositoryObserver`はallowlist済みのread-only Git commandだけを起動し、
HEAD、index、worktree、worktree listのmachine-readable snapshotを返す。`RecoveryInspector`と運用CLIは
Gitを直接起動できず、`RepositoryObserver`からsnapshotを受け取り、counterやjournal fileを直接編集しない。

### 4.1 状態機械

```text
LOCKED
  -> INTENT_DURABLE
  -> MUTATING
  -> RESULT_DURABLE
  -> DONE | QUARANTINED
```

- 各eventはoperation ID、target collision key、fencing token、単調sequence、直前digestを持つ。
- eventはowner-only temporary fileのfsync、atomic publish、directory fsyncで一度だけ公開する。
- 確定済みeventの上書き・削除・sequence再利用は禁止する。
- gap、branch、digest不一致、未知event、token巻戻り・overflowは`INDETERMINATE`にする。
- Git child終了までleaseを保持または監督し、終了状態を証明できなければ完了扱いしない。

### 4.2 緊急receiptを先行確定する

最初のGit mutation前に、同一filesystemへ次の2件をdurable公開する。

1. planned effectsとpreconditionを持つ`INTENT_DURABLE` event。
2. 「副作用が発生した可能性があり自動再実行不可」を示す有効な`INDETERMINATE`緊急receipt。

この2件を公開できなければGit副作用0件で`BLOCKED_STORAGE`を返す。正常終了時は新しいterminal receiptを
追記して緊急receiptをsupersedeするが、原本は削除しない。緊急receiptはjournal chain上のsequenceと
自分のdigestを持ち、後続terminal receiptは`supersedes_receipt_digest`でそれを指す。判定時は同一operationの
最長有効chainにある最後のterminal receiptだけを正とし、branchまたは複数の後継は`INDETERMINATE`にする。
nonceは`INTENT_DURABLE`の公開時点で消費済みとなる。したがってGit副作用後にENOSPCとなっても、
少なくとも安全側のoperator actionは既にdurableである。動的な最悪容量計算、予約file、archive容量管理は不要となる。

## 5. contract bundleと原子的promotion

### 5.1 単一bundle manifest

schemaごとのactivation manifestを廃止し、contract v2全体を1件のbundle manifestで管理する。

```text
bundle_version
contract_version
minimum_runtime_version
members[]              # schema ID, schema digest, codec ID, runtime module
platform_allowlist_digest
created_by_release
```

loaderはmember欠落、重複schema ID、未知field、schema/codec round-trip不一致を拒否する。
bundleはall-or-nothingであり、member単位の`active` / `reserved`状態を持たない。

### 5.2 promotion手順

promotionは通常operationと分離した明示的なlocal maintenance操作とし、次の順序に固定する。

1. owner-only promotion namespaceでexclusive local lockを取得する。
2. lock下でactive operation markerが0件であることを確認する。
3. 配布物のcode-owned member一覧からowner-only staging directoryへbundleを構築する。
4. staging内だけを読み、schema/codec round-trip、runtime version、platform allowlistを検証する。
5. current generationとruntime identityを再照合する。差異は`STALE`としてstagingをactiveにしない。
6. bundle directoryをfsyncし、generationとbundle digestを持つowner-only regular JSONの`current` pointerを
   atomic replaceしてdirectoryをfsyncする。
7. promotion receiptを追記し、lockを解放する。

未知artifactをchild processとしてprobeしない。stable launcherと公開CLIは起動時にcurrent bundleの
minimum runtimeとcontract versionを検査し、不一致・pending・未知bundleを`BLOCKED`にする。
exclusive lockとactive-operation 0条件により、registry generation CASや分散二段階commitを導入せず、
最終再照合からatomic publishまでを1つのローカルcritical sectionに閉じる。

通常applyはGit副作用前に同じpromotion lockを取得し、current bundleを再照合してowner-onlyの
active operation markerをdurable登録してからlockを解放する。terminal receipt確定後に再びlockを取得して
markerを解除する。promotionはlock保持中にmarkerが1件でもあれば`BLOCKED_ACTIVE_OPERATION`で停止する。
crashで残ったmarkerはread-only auditと明示確認付きreconcileがclosureを証明するまで削除しない。
これにより「0件確認の直後にapplyが開始する」競合をlocal lockだけで閉じる。

promotion lockとtarget lockは同時保持しない。applyはpromotion lockを解放してからtarget lockを取得し、
terminal receipt確定後にtarget lockを解放してからpromotion lockを再取得する。reconcileも同じ順序とする。
promotionはtarget lockを取得しない。この非重複規則をarchitecture testで固定し、lock待機はtimeout後に
副作用なしの`BLOCKED_LOCK_BUSY`を返す。

## 6. recoveryとquarantine

`audit`はread-onlyで、Git state、最長有効journal prefix、terminal receiptを照合し、次を返す。

- `confirmed-complete`: postconditionとterminal receiptが一致。
- `confirmed-incomplete`: 副作用なし、または予定postcondition未達を証明。
- `indeterminate`: child終了、journal、Git stateのいずれかを一意に証明できない。

自動解除、自動削除、自動再実行は行わない。運用者がGit状態を確認した後、`reconcile`を新しいplanと
`--confirm <operation_id>`で実行する。reconcileは同じtarget lock下で再照合し、既存のdecision digestと
一致する冪等なclosure eventだけを`TargetTransaction`経由で追記する。Git childは起動しない。
異なる判断、token不一致、状態変化は`STALE`とし、新しいauditからやり直す。

crash後のreconcile leaseは元operationのjournalを延長する`LOCKED` eventや新しいfencing tokenを
発行しない。OS target lockを再取得したうえで、auditが束縛したjournal headと元tokenが一致し、かつ
そのtokenがtarget authorityの現在最大値である場合に限ってclosure追記を許可する。これにより、後続
operationが開始済みの古いjournalへ復旧判断を後付けしない。

## 7. 最小運用面

公開する運用機能は次に限定する。

| 操作 | 状態変更 | 用途 |
|---|---|---|
| `worktree doctor` | なし | platform能力、bundle、lock、journal使用量の診断 |
| `worktree audit` | なし | Git stateと証跡の照合 |
| `worktree verify-receipt` | なし | event chainとterminal receiptの検証 |
| `worktree reconcile` | closure event追記のみ | 人間判断後の冪等な状態収束 |

read-only操作は実行前後のpersistent state digest不変を検査する。状態変更は同一OS owner、owner-only
namespace、明示確認を要求する。promotion/recovery/reviewerのRBAC、remote session policy、通知adapter、
運用RTOは設けない。resultは`result_code`、`cause_code`、`side_effect_state`、
`automatic_recovery_allowed`、closed `operator_action`、`operation_id`、`receipt_path`を持つ。

journal/receiptは自動削除、archive、prune、restoreしない。doctorは件数とbyte数を表示するが、
保持上限を理由に原本を変更しない。長期保持が実需要になった場合は、別のdiscovery、要件、Design Gateで扱う。

### 7.1 運用受入マトリクス

次の数値はservice SLOやRTOではなく、M2を公開可能と判定する**決定論的な受入条件**である。
reference fixtureは1 repository、2 local process、journal 10,000 event以下、receipt合計100 MiB以下とする。
時間条件は共有CIの性能SLOにせず、child/lockの有限timeoutとテスト完了上限だけを検査する。

| 事象 / 注入点 | 検出と観測 | 永続状態の期待 | 許可する操作 | 復旧完了条件 | 受入値 |
|---|---|---|---|---|---|
| plan後のHEAD/index/worktree/target変化 | apply再照合、`STALE` | intent・markerなし | 新しいplan | 新`operation_id`発行 | Git副作用0件、検出率100% |
| promotion lockまたはtarget lock競合 | timeout、`BLOCKED_LOCK_BUSY` | 取得済みでないlockやmarkerを残さない | timeout後に再plan | 競合process終了後の新plan | 同一targetのwrite-capable child最大1 |
| intent公開前のstorage error | `BLOCKED_STORAGE` | journal/receiptに部分公開なし | 容量・permission是正後に再plan | doctor green、新plan | Git副作用0件 |
| intent公開後〜Git child起動前のcrash | audit、緊急receipt | `INTENT_DURABLE`＋有効な緊急receipt | audit→reconcile | 単一closureまたはterminal receipt | 全注入点で有効chain 100% |
| Git child実行中・終了状態不明 | audit、`indeterminate` | worktree、marker、緊急receiptを保持 | 手動確認→reconcile | Git snapshotとdecision digestが一致 | 自動再実行0件、自動削除0件 |
| postcondition後〜terminal公開前のcrash | auditがGit stateとchainを照合 | 緊急receiptを正として保持 | audit→reconcile | terminalまたはclosureが単一後継 | 完了の推測0件 |
| terminal公開後〜marker解除前のcrash | doctor/auditがstale markerを検出 | terminal receiptとmarkerを保持 | reconcileでclosure証明後に解除 | active marker 0、chain有効 | 異decision解除0件 |
| journal gap/branch/digest不一致/token巻戻り | verify-receipt、`INDETERMINATE` | 原本保持、後続mutation停止 | manual inspection | 新しい裁定なしでは解除しない | fail-open 0件 |
| promotion中のmember欠落・generation変化・crash | loader/最終再照合/doctor | 旧currentまたは新currentの完全な一方 | staging隔離、再promotion | current digestと全member一致 | 部分active 0件 |
| doctor/audit/verify-receipt | 実行前後state digest | 完全不変 | 何度でも再実行 | 同じ入力で同じclosed result | 永続write 0件、結果一致100% |
| 同じdecisionのreconcile再試行 | decision digest照合 | closure eventは高々1件 | 冪等再試行 | 同一result/receipt参照 | 重複closure 0件 |
| network/unknown filesystemまたはsigned approval入力 | adapter/approval preflight | mutation stateを作らない | 対応local環境または別scopeへ移行 | `UNSUPPORTED_*`を保持 | Git副作用0件 |

reference fixtureの各行はLinux、macOS、Windowsの適用可能なregistered local profileで実行する。
platform固有で適用不能な注入は`N/A`理由を固定し、成功扱いに丸めない。doctor、audit、verify-receiptは
各commandがchild timeoutを含め30秒以内にterminal resultを返すfixtureを設け、timeout時もclosed resultを返す。

## 8. コンポーネントと依存方向

```text
CLI / Runtime
  -> ApprovalContext (plan-digest only)
  -> PlatformAdapter (observation/primitives)
  -> RepositoryObserver (read-only Git snapshot)
  -> PromotionBarrier (active-operation marker)
  -> MutationCoordinator (only Git launcher)
       -> TargetTransaction (lock/token/journal; no Git)

Doctor
  -> PlatformAdapter / ContractBundleLoader / PromotionBarrier (read-only)

Audit / VerifyReceipt
  -> RepositoryObserver (audit only)
  -> RecoveryInspector (read/decision)
       -> TargetTransaction (read only)

Reconcile
  -> ApprovalContext (new plan + explicit confirmation)
  -> RepositoryObserver (read-only re-observation)
  -> RecoveryInspector (closure decision)
       -> TargetTransaction (closure append only)

PromotionController
  -> ContractBundleLoader
  -> PlatformAdapter
```

禁止する依存は次のとおり。

- Contract kernelからOS、Git、subprocessへの依存。
- Platform adapterから承認・result policyへの依存。
- TargetTransaction、RecoveryInspector、PromotionController、運用CLIからGit childを直接起動する依存。
- RepositoryObserverからwrite-capable Git commandを起動する依存。
- Runtimeからjournal/counter fileを直接編集する依存。
- M2から鍵registry、archive backend、通知serviceへの依存。

### 8.1 エンドツーエンド接続

| フロー | 接続順 | 最終結果 | 所有task |
|---|---|---|---|
| plan | CLI → RepositoryObserver/PlatformAdapter → ApprovalContext | 副作用なしの`operation_id` | 106, 107, 109, 111 |
| apply開始 | CLI → ApprovalContext → PromotionBarrier登録 → TargetTransaction lock/intent/receipt | mutation前証跡確定 | 107, 108, 109, 113 |
| Git mutation | MutationCoordinator → write-capable Git child → RepositoryObserver再観測 → TargetTransaction terminal | `DONE`または`QUARANTINED` | 108, 109 |
| apply終了 | TargetTransaction lock解放 → PromotionBarrier marker解除 | promotion可能 | 108, 109, 113 |
| audit | CLI → RepositoryObserver → RecoveryInspector → TargetTransaction chain read | complete/incomplete/indeterminate | 108, 109, 110, 114 |
| verify-receipt | CLI → RecoveryInspector → TargetTransaction chain read | chain/result検証 | 108, 110, 114 |
| reconcile | CLI → ApprovalContext → RepositoryObserver → RecoveryInspector → TargetTransaction closure → PromotionBarrier解除 | Git mutationなしの状態収束 | 107, 108, 109, 110, 113, 114 |
| promotion | CLI → PromotionController → PromotionBarrier → ContractBundleLoader/PlatformAdapter → current pointer | 完全な旧bundleまたは新bundle | 106, 111, 112, 113, 114 |
| startup gate | stable launcher → minimum-runtime marker/current bundle | compatible時だけruntime起動 | 106, 112, 113 |

接続契約は、上流が下流のclosed resultを独自解釈せずそのまま伝播し、`operation_id`、
`collision_key`、fencing token、bundle generationのいずれかを途中で再生成しないこととする。
各フローの全edgeをintegration testで1回以上通し、未接続mockや公開CLIから到達不能な実装を出口未達とする。

## 9. task境界

| 順序 | 所有範囲 |
|---:|---|
| 1 | pure contract、plan-digest、単一bundle schema |
| 2 | platform adapter、static allowlist、case collision key |
| 3 | TargetTransaction、lease、fencing、journal、緊急receipt |
| 4 | minimum-runtime gateとatomic bundle promotion |
| 5 | MutationCoordinatorへの結線 |
| 6 | audit、reconcile、doctor、runbook |

各taskは担当module、schema、codec、testを同じrollback単位に含める。各実装PRの先頭taskをrelease
integration ownerとし、`flow-core/SKILL.md`、bitz-flowの3マニフェスト、root marketplaceをそのtaskの
boundaryへ含め、PRごとにpluginとskillをpatch bumpする。ownerはPR 1=`106`、PR 2=`111`、PR 3=`108`、
PR 4=`112`、PR 5=`109`、PR 6=`110`とする。schema別activation file、署名policy、reviewer registry、
archive schema、通知adapterはtask boundaryに含めない。

### 9.1 残作業の再見積もり

設計是正以前の実績はsunk costとし、再Design Gate後の残作業だけを数える。1 PRは1関心事とし、密接な
pure contractまたは運用結線だけを同じPRへまとめる。sessionは実装・テスト・レビュー修正を含む上限である。

| 実装PR | task | 内容 | session上限 | 停止条件 |
|---:|---|---|---:|---|
| 1 | 106, 107 | pure contract、用語codec、plan-digest | 3 | closed schemaまたはsigned入力拒否が確定しない |
| 2 | 111 | 3platform adapter、collision key、static allowlist | 3 | registered local fixtureのlogical parity未達 |
| 3 | 108 | TargetTransaction、fencing、journal、緊急receipt | 4 | 全crash pointで有効chain 100%未達 |
| 4 | 112, 113 | minimum-runtime、PromotionBarrier、atomic promotion | 3 | 部分active 0件またはapply/promotion相互排他未達 |
| 5 | 109 | RepositoryObserver、MutationCoordinator、runtime結線 | 3 | write-capable Git childの迂回経路または未接続edgeが残る |
| 6 | 110, 114 | audit、verify、reconcile、doctor、runbook、E2E | 4 | 運用受入マトリクスに未実行行またはoperator action欠落が残る |

合計は**6 PR / 20 session**。PRまたはsessionのどちらかを使い切った時点で実装を停止し、未達行、
実績、scope変更候補を人間へ再提示する。PR 1/2は機能依存がないがrelease metadataを共有するため直列化し、
PR 3以降も上表とtaskの`depends_on`に従う。設計・裁定・spec reviewは実装budgetへ数えない。

## 10. 検証設計

- plan-digestの正常系、期限切れ、nonce再利用、context差替えを検査する。
- `signed-capability`入力が無言降格せずGit副作用0件で停止することを検査する。
- case-sensitive / insensitive、不在target、NFC/NFD、symlink/reparse pointを検査する。
- 2process以上の競合でmutationへ進むprocessが最大1つであることを検査する。
- 全phaseのcrash injectionで緊急receiptまたはterminal receiptが残ることを検査する。
- counter巻戻り・overflow、journal gap/branch/改変を安全側へ停止する。
- bundle member欠落、codec不一致、promotion競合、active operation存在時に部分activeを残さない。
- network/unknown filesystemを拒否し、登録済み3platform local fixtureの通常系を通す。
- doctor/audit/verifyのpersistent state digestが不変であることを検査する。
- reconcileの同一decision retryが同じ結果へ収束し、異decisionが`STALE`になることを検査する。
- RepositoryObserverのallowlist外command、write option、porcelainでない出力要求を拒否する。
- 8.1の全edgeと7.1の全適用行をcoverage manifestへ記録し、未接続edgeと未実行行を0件にする。

## 11. FLW-REV-024への対応

| Finding | 対応 |
|---|---|
| SYN-001 | `TargetTransaction`をlock/token/journalの単一authorityにする |
| SYN-002 | 未知artifact child probeを廃止し、owner-only staging内のdata検証へ限定する |
| SYN-003 | exclusive promotion lockとatomic current pointer publishでcritical sectionを閉じる |
| SYN-004 | 署名releaseを廃止し、明示確認付きreconcileの冪等closureへ置き換える |
| SYN-005 | 署名policy・reviewer registry・root of trustをM2 scope外にする |
| SYN-006 | archive・prune・restoreをM2 scope外にし、原本を削除しない |
| SYN-007 | mutation前に有効な緊急receiptをdurable公開する |
| SYN-008 | schema別activationを単一all-or-nothing bundleへ置き換える |
| SYN-009 | 表示pathとcase-aware collision keyを分離する |
| SYN-010 | RBACをscope外にし、同一OS ownerと明示確認を認可境界にする |
| SYN-011 | 運用commandを既存`worktree <action>`の2階層へ固定する |
| SYN-012 | RTOをscope外にし、既存の結果完全性とfixture実行時間だけを測る |

## 12. ロールバック

設計・要件・task変更は1つの変更セットとしてrevertできる。実装後のrolloutは`audit-only`、
`promotion-ready`、`canary`、`default-on`の順とし、各段階でM0 read-only公開面へ戻せる。
contract v2 bundleを一度activeにしたrepositoryは、current pointerを既知のcompatible bundleへだけ戻せる。
pre-v2 runtimeへ戻す場合はv2 stateを無視せず、doctorが明示するmanual rollback手順を要求する。

## Revision History

- 2.2 (2026-08-22) 実装前検査の裁定を反映。legacy schemaとactive bundleを分離し、非対応承認方式の
  公開result写像、PRごとのrelease integration ownerと直列化を確定
- 2.1 (2026-08-22) 用語表、運用受入マトリクス、RepositoryObserverを含むE2E接続表、
  9taskに基づく残作業6 PR/20 sessionの再見積もりを追加
- 2.0 (2026-08-22) M2 Local Safety Profileへ縮退。plan-digest限定、単一TargetTransaction、
  緊急receipt、単一bundle promotion、最小運用面を採用し、署名policy・archive・RBAC・通知/RTOを除外
- 1.5 (2026-08-22) Safety KernelとOperations Control Planeを分離し、不変operation journal、運用CLI、
  reviewer key lifecycle、support/retention profile、4段階rollout、責務別task境界を追加
- 1.4 (2026-08-22) FLW-REV-023のP1〜P3を反映し、native path、identity kind、schema activation所有権、
  trusted promotion、quarantine管理経路、token/digest/SemVer契約を確定
- 1.3 (2026-08-22) NFD拒否境界、platform別file identity、active/reserved codec整合、実entrypoint probeを具体化
- 1.2 (2026-08-22) promotion barrierとminimum-runtime rollback境界を追加
- 1.1 (2026-08-22) FLW-REV-021のGP-001〜005を反映し、旧runtimeへの遡及保証を撤回
- 1.0 (2026-08-22) FLW-NFR-014の初期設計
