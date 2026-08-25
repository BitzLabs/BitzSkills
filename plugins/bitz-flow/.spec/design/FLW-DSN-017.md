---
id: FLW-DSN-017
title: "M2 Local Safety Profileの競合排除・耐久証跡・原子的promotion"
status: active
version: 2.8
updated: 2026-08-24
owner: codex
implements: FLW-NFR-014, FLW-CON-008
origin: SI-FLW-077, SI-FLW-078, SI-FLW-079, SI-FLW-080, SI-FLW-081, SI-FLW-082,
  SI-FLW-084, SI-FLW-085, SI-FLW-086, SI-FLW-087, SI-FLW-088, SI-FLW-089, SI-FLW-090
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
  ここでいう「残る」は**永続filesystem上**での話である。`tmpfs`はマシン再起動で消えるため
  この保証が成立せず、allowlistから外している（`FLW-REV-028:GP-007`）。worktree rootの既定は
  `<repo-parent>/.worktrees/...`（`FLW-DSN-006`）であり永続filesystem上にある。
- 完了を証明できない操作を`INDETERMINATE`または`QUARANTINED`として保持する。
- contract v2を部分activeにせず、単一bundleとして原子的に有効化する。
- **Linux**の登録済みlocal filesystem adapterでlogical resultへ収束する。
  macOS／Windowsは**当面保証対象外**とし、probeは`platform-out-of-scope`で閉じる
  （裁定 2026-08-24。`FLW-REV-028:GP-003`。実装は残す。再開条件は
  `.spec/reports/decision-2026-08-24-linux-only-scope.md`）。

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
| `target OS` | probeと`PlatformAdapter`が対象とする実行OS（Linux／macOS／Windows） | `PlatformAdapter` | 対象OSの追加・削除まで |
| `agent platform` | confirmationの被験エージェントCLI（claude／codex／antigravity） | confirmation runner | 対象CLIの追加・削除まで |

本文、schema、result、runbookはこの用語を正とし、`approval token`、`lease receipt`、`active manifest`などの
別名を導入しない。OS固有名は`PlatformAdapter`内部に閉じ、公開resultでは上表のlogical nameへ正規化する。

**「platform」を単独で使わない**（`SI-FLW-092`）。本設計では2つの異なる軸に同じ語が
使われており、混同すると**片方の達成をもう片方の達成として読める**。

- `target OS` は **OS** の軸である。Linux／macOS／Windowsの実行環境を指し、
  §13.5 platform reality表と`FLW-NFR-014`の`verified`昇格条件が要求する「実観測」は
  **この軸**である。
- `agent platform` は **エージェントCLI** の軸である。confirmationが同一test ID集合を
  claude／codex／antigravityで実行することを指す。**3者とも同一ホスト上で走る**ため、
  これが揃っても`target OS`の実観測にはならない。

2026-08-24のconfirmationは`agent platform` 3者PASSであり、`target OS`の実観測は
Linuxのみである。

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
- case-insensitiveと判定した環境は`case-insensitive-unsupported`で`UNSUPPORTED_FILESYSTEM`
  とする。`collision_key`が要求するfolded_componentのfolding規則を、実物の
  case-insensitive volumeを観測できない環境で新設しない（`FLW-REV-028:GP-005` 案B）。
- case-insensitiveかどうかを安全に判定できない不在targetも`UNSUPPORTED_FILESYSTEM`とする。
- Unicode normalizationで別directory entryを同一scopeへ畳み込まない。

### 3.2 platform adapter

platform adapterはpolicyを決めず、owner、ACL/mode、非追随walk、regular file/directory identity、
case semantics、OS lock、file/directory durability、child process監督のclosed evidenceだけを返す。

サポート対象は**保証scope**（当面Linuxのみ）とコード同梱の静的allowlistで決める。
allowlistは永続local filesystemに限る（`btrfs` / `ext4` / `xfs`）。

**probeが検査するもの・しないもの**（`FLW-REV-028:GP-007`）。probeは**read-only**であり
対象filesystemへ書き込まない。したがって検査できる範囲には限界があり、それを明示する。

| 項目 | probeの検査 | 根拠 |
|---|---|---|
| platform / filesystem種別 | mount pointの最長一致で**実測** | `/proc/self/mountinfo` |
| owner / ACL | `st_uid` と mode を**実測** | `os.stat` |
| symlink非追随 | component単位の`lstat`で**実証** | 経路上のsymlink検出 |
| case semantics | 対象entryのlookupで**実測** | 同一parent内の反転引き＋inode一致 |
| OS lock / durability / child監督 | **primitiveの可用性のみ**（semanticsは未実証） | allowlistを信頼する |

**lock・durabilityの実semanticsは検査していない。** `flock`がno-opな環境や`fsync`が嘘をつく
環境は、allowlistと`filesystem-class-network`拒否で先に排除される前提に依存している。
実証するには対象filesystemへ書き込む必要があり、read-only commandの
`persistent write 0件`保証（§7.1 `readonly-invariance`）と衝突するため採らない。

以前の版は「起動時semantic self-test」を要求していたが、実装は
`_semantic_self_test`が直前に変換成功した値を同じcodecで往復させるだけの**恒真**関数で
あり検査になっていなかった。関数とevidence fieldを撤去し、本表のとおり書き直した。

**再検討の条件**: allowlistへ新しいfilesystemを追加するとき、またはnetwork/FUSEの拒否を
緩めるときは、lock・durabilityのsemanticsを実証する手段を先に用意すること。
self-testだけで未知filesystemをsupportedへ格上げしない。support profileへの署名や
外部更新機構は持たない。

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

### 4.2 intentと緊急receiptを単一durable recordで確定する（2.3で変更）

**v2.2の欠陥**: `prepare_intent`は`INTENT_DURABLE` eventのatomic publishと緊急receiptの
atomic publishを**2回に分けて**行っていた（`worktree_transaction.py` L197-L209）。この2回の間で
停止すると、chain検査`len(events) >= 2 and len(emergency) != 1`（同 L323-L324）が
`durable intent does not have exactly one emergency receipt`を記録し、chainは`INDETERMINATE`になる。
このときGit副作用は**証明可能に0件**（`mark_mutating`が`require_emergency=True`を要求するため
`MUTATING`へ進めない）であるにもかかわらず、nonceは`INTENT_DURABLE`公開時点で消費済みである。
結果として、**副作用0件のtargetが同一planで再実行できないまま隔離される**。
これはFLW-NFR-014のdurable receipt受入基準に反する。

**2.3の設計**: intentと緊急receiptを**単一のdurable transaction record**として1回のatomic publish
（temp write → file fsync → rename → directory fsync）で公開する。最初のGit mutation前に確定するのは
次を含む1件だけとする。

1. planned effectsとprecondition。
2. 「副作用が発生した可能性があり自動再実行不可」を示す`INDETERMINATE`緊急receipt。
3. nonce digestとfencing token。

この1件を公開できなければGit副作用0件で`BLOCKED_STORAGE`を返す。record公開の前後どちらで停止しても
中間状態は存在せず、`INTENT_DURABLE`は「intentと緊急receiptが同時に確定した」ことだけを意味する。
nonceの消費はこのrecordの公開と同時に成立し、部分公開による消費は起こらない。

正常終了時は新しいterminal receiptを追記して緊急receiptをsupersedeするが、原本は削除しない。
terminal receiptは`supersedes_receipt_digest`でrecord内の緊急receipt digestを指す。判定時は
同一operationの最長有効chainにある最後のterminal receiptだけを正とし、branchまたは複数の後継は
`INDETERMINATE`にする。したがってGit副作用後にENOSPCとなっても、安全側のoperator actionは既にdurableである。
動的な最悪容量計算、予約file、archive容量管理は不要である。

**移行**: 旧形式（分離publish）のchainは推測移行せずfail-closedとし、doctorがmanual rollback手順を
提示する。schema・runtime・testを同一rollback単位に置く（`SI-FLW-087`）。

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

## 13. 実証設計（FLW-CON-008）

本節は`FLW-CON-008`が要求する6表である。**本節の各行は現時点の実測に基づき、未接続を
未接続として記載する。** `FLW-REV-027`のFAILは、v2.2 §8.1が接続順を書いていたにもかかわらず
production経路の到達可能性を検査しなかったことに起因する。したがって本節は「設計上の意図」ではなく
**「production既定dispatcherから到達するか」の実測結果**を記す。

### 13.1 垂直接続図

production入口は`skills/flow-core/scripts/flow.py`が呼ぶ`flowlib/cli.py`の`main()`既定表
`_HANDLERS`とする。black-box testは`flow.py`を別processとして起動し、handler注入を行わない。`main(handlers=...)`は
fixture専用注入口であり、**本表のproduction test ID欄にfixture注入testを記載してはならない**。

| # | フロー | production入口 | 経由component | 最終永続証跡 | 利用者出力 | 所有task | production test ID |
|---:|---|---|---|---|---|---|---|
| 1 | `repo.inspect` | `_HANDLERS` 到達 | RepositoryObserver | なし（read-only） | `OK` + snapshot | M0既存 | `tests/test_flow_m1_contract_rows.py::test_reachable_codes_are_still_m0_only` |
| 2 | `git.status` | `_HANDLERS` 到達 | RepositoryObserver | なし（read-only） | `OK` + status | M0既存 | `tests/test_flow_m1_contract_rows.py::test_reachable_codes_are_still_m0_only` |
| 3 | `git.diff-summary` | `_HANDLERS` 到達 | RepositoryObserver | なし（read-only） | `OK` + diff | M0既存 | `tests/test_flow_m1_contract_rows.py::test_reachable_codes_are_still_m0_only` |
| 4 | `worktree.*` 全8件の非公開 | `_HANDLERS` 非到達 | dispatcher の`UNSUPPORTED`写像 | なし | `UNSUPPORTED` / `command-unavailable` | 113 | `tests/test_flow_m2_runtime.py::test_worktree_remains_unreachable_from_public_dispatcher` |
| 5 | 旧signed-capability拒否 | `--capability-file`検出 | cli.py L916-L930 | なし | `UNSUPPORTED` / `unsupported-approval-mode` | 085 | **未実装**（現行testはfixture注入経路） |
| 6 | `worktree.create` plan | **未接続**（gated） | PlatformProbe → ApprovalContext → RuntimePlan | plan digest | `OK` + `operation_id` | 116 | **未実装**（公開集合復帰後。probe結線は`tests/test_flow_m2_platform_probe.py::test_plan_no_longer_requires_injected_platform_evidence`） |
| 7 | `worktree.create` apply | **未接続** | TargetTransaction → MutationCoordinator → Git child | 単一intent record → terminal receipt | `DONE` / `QUARANTINED` | 084, 086, 087 | **未実装** |
| 8 | `worktree.resume` | **未接続** | 同上（binding検証つき） | 同上 | `DONE` / `QUARANTINED` | 084, 085, 087 | **未実装** |
| 9 | `worktree.audit` | **未接続** | RepositoryObserver → RecoveryInspector | chain read（追記なし） | complete / incomplete / quarantine | 088 | **未実装** |
| 10 | `worktree.reconcile` | **未接続** | ApprovalContext → RecoveryInspector → closure追記 | closure event | 状態収束 | 089 | **未実装** |
| 11 | `worktree.doctor` | **未接続**（gated） | PlatformProbe → ContractBundleLoader | なし | 診断結果 | 116 | **未実装**（公開集合復帰後。共通生成器は`tests/test_flow_m2_platform_probe.py::test_plan_and_doctor_share_one_evidence_generator`） |

**実測根拠**: 行6〜11が未接続である理由は、8つの`worktree.*` handlerがすべて
`_GATED_HANDLERS`にあり`_HANDLERS`に無いこと（`cli.py`）である。これは縮退規則3による
意図的なgatingであり、解除は`FLW-REV-027`のGate blocking条件を満たしたときに限る。

`FLW-TSK-116`以前は、より根本的な断線があった。`worktree_runtime.plan()`が
`platform_evidence is None`のとき`platform evidence is required`を送出する一方で、
`PF.evaluate_platform()`を呼ぶproduction呼出元が存在せず、`PlatformObservation`を
構築するコードも無かった。**公開集合へ戻しただけでは必ず例外で停止する状態**だった。
`FLW-TSK-116`で実環境probeを実装し、`plan()`とdoctorを共通生成器
`platform_evidence_for()`へ結線してこれを解消した。残るのはgatingのみである。

**接続契約**: 上流は下流のclosed resultを独自解釈せずそのまま伝播し、`operation_id`、
`collision_key`、fencing token、bundle generationを途中で再生成しない。
行が`実証済み`となる条件は、production既定dispatcherを起点とするblack-box testの実在である。

### 13.2 状態遷移意味表

| 状態 | 前提 | 永続証跡 | 許される後続処理 | 禁止される完了判定 |
|---|---|---|---|---|
| `DONE` | terminal receiptが最長有効chainの最後にあり、予定postconditionが観測で成立 | terminal receipt（`supersedes_receipt_digest`が緊急receiptを一意に指す） | lock解放、marker解除、promotion可 | 予定postconditionを検証せず`DONE`にすること |
| `QUARANTINED` | mutation後の再観測が予定postconditionと不一致 | terminal receipt（`QUARANTINED`）＋`RESULT_DURABLE`へ束縛したrequested outcomeと予定effects | audit報告、人間判断、reconcileによるclosure | **`confirmed-complete`へ分類すること**（`FLW-TSK-119`で是正済み。現在snapshotの一致を根拠にしない） |
| `INDETERMINATE` | chainにgap／branch／digest不一致／未知event／token巻戻り、または終了状態を証明できないGit child | 最長有効prefixまでのevent（追記は行わない） | 新planと明示確認によるreconcile | 現在snapshotが期待と一致することを根拠に`DONE`扱いすること |
| `UNSUPPORTED` | 環境が保証対象外（platform／filesystem／case semantics／owner-only 不成立）。**Git副作用0件** | 永続証跡なし（plan前に停止） | 環境是正後の再実行 | `BLOCKED`（競合）と同一視すること。理由だけ示して operator action を省くこと |
| `BLOCKED` | precondition不成立、lock競合、storage不能。**Git副作用0件** | `BLOCKED_STORAGE`時はrecord未公開 | 原因解消後の同一planでの再実行 | 副作用の有無を確認せず失敗を成功へ畳むこと |

**operator action の義務**（`FLW-REV-028:GP-001`）: `recovery_class: human-stop` の
closed resultは`data.required_human_input`へ**行動可能な**是正を載せる。理由の写しでは
足りない。とくに`acl-not-owner-only`は**既定umask（0755）のworktree rootが必ず拒否される**
条件であり、対象pathと必要mode（0700）を明示する。理由と是正の対応表は
`worktree_platform.OPERATOR_ACTIONS`を正とし、`evaluate_platform`が出す全理由を
網羅することを機械検査する。手順は`docs/runbooks/m2-worktree-quarantine.md`。

**不変条件**: `QUARANTINED`と`INDETERMINATE`はいかなる経路でも`DONE`または`confirmed-complete`へ
畳み込まない。`confirmed-complete`は`DONE`**かつ**予定postcondition成立時に限る（`SI-FLW-088`）。

**実装状況**（`FLW-TSK-119`）: `worktree_recovery.audit()`はこの限定を満たす。旧実装は
`QUARANTINED`を完了判定の集合に含めており、記録される`postcondition_digest`が*予定*ではなく
*実観測*の値であるため、quarantine後にrepositoryが変化していなければ現在snapshotと一致して
`confirmed-complete`へ分類されていた。`RESULT_DURABLE` eventへrequested outcome
（`terminal_state`）と`planned_effects_digest`を束縛し、実観測値だけで完了を主張できないようにした。
終局event未着（`RESULT_DURABLE`止まり）でも、要求された結末が`QUARANTINED`なら完了へ倒さない。
陽性・陰性対照は`tests/test_flow_m2_outcome_binding.py`（9 test）。

### 13.3 crash-point表

durable writeは4段階（temp write → file fsync → rename → directory fsync）のatomic publishで行う。
本表は各publishの直前・直後で停止した場合を列挙する。

| # | durable write | 直前で停止 | 直後で停止 | authority | 再開処理 | 重複実行時の結果 |
|---:|---|---|---|---|---|---|
| 1 | `LOCKED` event | lock未取得。証跡なし | lock保持、intent無し | TargetTransaction | lock期限切れ後に再取得し同一planで再実行 | 冪等（同一sequenceの再利用は拒否） |
| 2 | **単一intent record**（2.3統合。`FLW-TSK-118`で実装） | nonce未消費、Git副作用0、状態は`LOCKED` | nonce消費、緊急receipt有効、Git副作用0、状態は`INTENT_DURABLE` | TargetTransaction | 緊急receiptを根拠にreconcileで安全closure | 冪等（nonce再消費を拒否） |
| 3 | `MUTATING` event | intent record確定済、Git未起動 | Git起動可、副作用未確定 | MutationCoordinator | 再観測して`DONE`／`QUARANTINED`を判定 | Git child再起動は禁止。再観測のみ |
| 4 | Git child実行中 | 副作用0 | 副作用の有無が不明 | MutationCoordinator | 再観測。証明不能なら`INDETERMINATE` | 自動再実行不可（緊急receiptが明示） |
| 5 | terminal receipt | 副作用確定済、緊急receiptのみ有効 | terminal確定、緊急をsupersede | TargetTransaction | chain最長有効prefixから終局判定 | 冪等（複数後継は`INDETERMINATE`） |
| 6 | reconcile closure | marker適格性は確認済み（closure未追記） | closure確定、marker未解除 | RecoveryInspector | marker適格性はclosure**前**にpromotion lock下で確定済み（`FLW-TSK-120`）。marker解除のみ再試行 | 同一decisionの再試行は単一closureへ収束 |
| 7 | promotion marker解除 | marker保持、promotion不可 | marker解除、promotion可 | PromotionBarrier | marker再検証 | 冪等 |

**v2.2からの解消**: 旧設計は#2を2回のpublishに分割しており、その間の停止が
「Git副作用0件かつnonce消費済みかつ`INDETERMINATE`」という回収不能状態を作っていた（§4.2）。
2.3の統合によりこの空隙は構造的に消える。

**実装状況**: #6は`FLW-TSK-120`で解消済み（適格性検査をclosure前へ移動）。#2は`FLW-TSK-118`で解消済み。4つのpublish step全点でkillして検証しており、rename前は`LOCKED`（receipt 0件）、rename後は`INTENT_DURABLE`（receipt 1件）となり、**「intent確定かつ緊急receipt無し」は生じない**（`tests/test_flow_m2_intent_atomicity.py::test_no_crash_point_leaves_a_durable_intent_without_an_emergency_receipt`）。#4の有限収束は`FLW-TSK-117`で結線済み。**crash-point表の全行が実装・検証済みになった。**
`target lock`と`promotion lock`を同時保持しないlock order不変条件は維持している。適格性検査はpromotion lockを取り、**target lockを取る前に解放する**（`tests/test_flow_m2_marker_eligibility.py::test_promotion_lock_is_never_held_while_holding_the_target_lock`がASTで機械検査）。

### 13.4 liveness budget表

全Git childは`worktree_runtime._supervised_git()`経由で`process.run()`の監督下に入る
（`FLW-TSK-117`）。budgetは`process.normalize_timeout()`が範囲へ丸めるため、
**要求値が何であれ有限かつ正になる**（`None`／`0`／負値／`inf`のいずれも丸められる）。

| 対象 | deadline | kill手順 | 出力回収 | terminal result最大応答 |
|---|---:|---|---|---:|
| **operation全体** | **30秒**（`DEFAULT_OPERATION_DEADLINE_SECONDS`） | 残り時間が尽きたらchildを起動しない | — | **30秒**（`FLW-NFR-014`受入基準） |
| read-only Git child | 残り時間と30秒の小さい方 | SIGTERM → 2.0秒grace → SIGKILL（Windowsはjob object close） | 8 MiB上限。超過で終了させ`UNAVAILABLE` | operation deadline内 |
| snapshot観測child | 残り時間と30秒の小さい方 | 同上 | **64 MiB**（`SNAPSHOT_OUTPUT_LIMIT_BYTES`。専用設計値） | operation deadline内 |
| write-capable Git child | 残り時間と30秒の小さい方。executionは60% | SIGTERM → grace（総量の10%、1〜5秒） → SIGKILL | 8 MiB上限 | operation deadline内 |

**operation全体のdeadline**（`FLW-REV-028:GP-002`）: child単位のbudgetだけでは保証が成立しない。
1 operationは`snapshot()`（4 child）をplan／apply／postで複数回回すため**15〜20 child**を
起動し、child毎30秒なら最悪450秒超になる。`OperationDeadline`が各childへ**残り時間**を配り、
尽きたらchildを起動せず`operation-deadline`として閉じる。plan と apply は別の起動なので
deadlineもそれぞれ開始する（planの残りをapplyへ持ち越さない）。
child単位のbudgetは二重の網として残す。

**snapshot観測の出力上限**: `git status --porcelain=v2 -z --untracked-files=all`は未追跡
ファイルが多いrepositoryで既定のchild上限（8 MiB。porcelain=v2の未追跡行は概ね
`? <path>\0`なので約13万件相当）を超えうる。snapshotはoperationの必須経路であり、
既定値の流用では大規模repositoryでplan自体が失敗する。専用の設計値として分離する。

**負荷条件での収束（実測）**: 10,000 eventのjournalに対する`inspect()`の収束を実測した。

| 条件 | 実測 | 要求 |
|---|---:|---:|
| 10,000 event の chain 検査 | **0.40秒** | 30秒 |

測定は`tests/test_flow_m2_operation_budget.py::test_chain_inspection_converges_under_load`。
chain検査は全eventを読むため線形に伸びるが、要求に対して2桁の余裕がある。

**timeoutの写像**: timeoutは「失敗」ではなく「副作用の有無が不明」である。
`WorktreeChildTimeoutError`を専用に設け、write childのtimeoutを`QUARANTINED`
（再観測が予定postconditionと不一致＝観測はできた）へ畳まず`INDETERMINATE`へ閉じる。
§13.2の「終了状態を証明できないGit child」と一致する。CLIは同errorを
`INDETERMINATE` / `result-indeterminate`のclosed resultへ写す。

**`--timeout-seconds`の伝播**: CLIの`--timeout-seconds`は`plan()`へ渡り、
`RuntimePlan.timeout_seconds`としてapply経路の全childへ伝播する。以前はM0 read
operationにだけ渡り、worktree経路へは渡っていなかった。

**解消済みの乖離（v2.3時点の記録）**: v2.3時点では`process.py`が`TimeoutBudget`・SIGTERM/SIGKILL・
2.0秒grace・8 MiB出力上限・Windows job objectを実装済みである一方、
`worktree_runtime.py`の全subprocess呼び出しが素の`subprocess.run`で`timeout=`を
持たず、hangしたGit childが無期限にブロックしていた。`FLW-TSK-117`で3つのGit
呼び出しを`process.run()`へ置換し、素の`subprocess.run`を0件にした
（`tests/test_flow_m2_liveness.py::test_worktree_runtime_never_spawns_an_unsupervised_child`）。
あわせて呼出元0件のまま無制限openssl childを起動していた死コード`ed25519_verifier`を除去した。

**未達**: 100 MiB規模のjournal容量そのものに対する測定は未実施である（event数での測定は実施済み）。

### 13.5 platform reality表

registryの正は`skills/flow-core/references/worktree-v2-platform-support.json`とする。
probeの正は`worktree_platform.probe_platform()`で、planとdoctorは共通入口
`platform_evidence_for()`を通る（`FLW-TSK-116`）。probeは**read-only**であり、
対象filesystemへ書き込まない。

| OS | 実装component | identity | probe方法 | 未対応時の即時拒否 | 実観測 |
|---|---|---|---|---|---|
| linux（**保証対象**） | flock / fsync / fsync / waitpid | uid（`st_uid` vs `geteuid`） | `/proc/self/mountinfo`を`st_dev`（major:minor）で引きfstypeを得る。case semanticsはswapcase pathの存在で判定 | `UNSUPPORTED_FILESYSTEM` | **実施**（`tests/test_flow_m2_platform_probe.py::test_probe_observes_the_real_filesystem`。Linux 6.18 WSL2 / ext4・tmpfsで`SUPPORTED`、9pで`filesystem-class-network`を確認） |
| macos（**保証対象外**） | flock / fsync / fsync / waitpid | uid | `statfs(2)`の`f_fstypename`をctypesで取得。case-insensitive volumeを含む | `UNSUPPORTED_FILESYSTEM` | **対象外**（実装は残す。既定APFSがcase-insensitiveでfolded_component導出不可） |
| windows（**保証対象外**） | LockFileEx / FlushFileBuffers / ReplaceFileW / job-object | sid | `GetVolumeInformationW`でfilesystem名と`FILE_CASE_SENSITIVE_SEARCH`を取得 | `UNSUPPORTED_FILESYSTEM` | **対象外**（実装は残す。SID取得手段が未確定で`owner-unobservable`固定） |

**実証の義務**（`FLW-REV-028:GP-006`／`GP-008`）: probeは検証していない性質を主張しない。

- `non_follow_walk`は primitive の可用性**だけでは主張しない**。要求されたpath（`resolve()`
  **前**）をcomponent単位に`lstat`し、経路上にsymlinkが無いことを実証する。
  `resolve()`後を検査しても常に「symlink無し」になるため意味がない。
- case semanticsは**mount局所**で判定する。絶対path全体のswapcaseは祖先のcase差に
  引きずられる。対象entry名だけを反転して同一parent内で引き、見つかった場合は
  `(st_dev, st_ino)`一致で同一entryかを確かめる（同名の別entryをinsensitiveと誤認しない）。
- filesystem種別は**mount pointの最長一致**で選ぶ。`st_dev`（major:minor）はbind mount間で
  共有されるため識別子として不十分で、先頭一致では親マウントの種別を返す。
- いずれも判定材料が無ければ`None`を返し不支持へ閉じる。**推測しない。**

**代替禁止**: 他OSのcomponentによる代替を同一証明として扱わない。registryが宣言する
`child_supervision`と実runtimeで使える primitive が食い違う場合は`supported`にしない
（`test_child_supervision_must_match_the_declared_primitive`）。

**fail-closed**: probeは**例外を送出しない**。観測不能・未知filesystem・network filesystemは
`supported`へ格上げせず、理由をclosed evidenceの`reasons`へ載せる。`fuse.*`は既知の
network transportとして扱い、未知の`fuse.*`変種もlocalへ格上げしない。support registryが
読めない場合も`support-registry-unreadable`として閉じる。

**Windowsの残課題**: `_owner()`はWindowsでSIDを取得できないため`owner_principal=None`を返し、
`owner-unobservable`で必ず不支持になる。これは安全側の既定であり誤りではないが、Windowsを
supportedにするにはSID取得の実装が要る。`SI-FLW-084`の残作業として本表に明示する。

### 13.6 legacy exclusion表

到達不能性の確認手段は2種類ある。`--capability-file`は公開可否より先に閉じるため
**production black-box**で観測できる。宣言fileとtrusted key registryの検出は、worktree
operationがgatedである間production入口から到達できず`command-unavailable`に隠れるため、
到達不能性を**production codeの参照0件**で確認する。参照0件は`SI-FLW-084`で公開集合へ
戻したあとも維持され、その時点でblack-boxのnegative testへ置き換える。

| 廃止対象 | 所在 | production入口からの到達可否 | 即時拒否の写像 | negative test ID |
|---|---|---|---|---|
| `--capability-file`（signed capability） | `cli.py` `main()` | 到達する（gatingより前の拒否handler） | `UNSUPPORTED` / `unsupported-approval-mode` | `tests/test_flow_m2_legacy_approval.py::test_capability_file_is_rejected_as_unsupported_approval_mode` |
| capability fileの内容解析 | 除去済み | 到達しない（内容を読まない） | 同上 | `tests/test_flow_m2_legacy_approval.py::test_capability_file_content_is_never_parsed` |
| `resolve_approval_mode` | 除去済み | 参照0件 | 共通preflightへ一本化 | `tests/test_flow_m2_legacy_approval.py::test_production_cli_does_not_reference_retired_approval_symbols` |
| trusted key registry選択 | 除去済み | 参照0件 | 同上 | 同上 |
| openssl署名検証child | 除去済み（到達不能`audit`分岐ごと） | 参照0件 | 経路ごと除去 | 同上 |
| `worktree_dir_guard_key` 旧context | 除去済み | 参照0件 | `ApprovalContext.target_collision_key`へ一本化 | 同上 |
| 旧宣言 / trusted key registryの存在検出 | `worktree_operability.has_unsupported_approval_input` | gated（`command-unavailable`に隠れる） | `UNSUPPORTED` / `unsupported-approval-mode` | **未実装**（公開集合復帰後にblack-box化） |
| legacy signed-capability schema | `schemas/worktree-v2/` | bundle memberではない（実在のみ） | active bundleへ混入させない | `tests/test_flow_m2_contract_v2.py` |

**契約**: 廃止入力は**内容を解析せず**mutation前に閉じる。解析してからの降格、
`plan-digest`への暗黙のfallbackを禁止する。存在しないpath・壊れたJSON・必須field欠落の
いずれでも同一の`unsupported-approval-mode`を返すことで、内容非依存であることを示す
（`FLW-TSK-115`で実装）。

### 13.7 7観点の現状

`FLW-CON-008`が要求するDesign Gateへの回答である。

| # | 観点 | 現状 | 根拠 |
|---:|---|---|---|
| 1 | 接続完全性 | **未実装境界** | 13.1 行6〜11が`_HANDLERS`非到達。evidence生成器不在は`FLW-TSK-116`で解消し、残るのはgatingのみ |
| 2 | 失敗原子性 | **検証計画** | 13.3 全行が実装・検証済み（#2は`FLW-TSK-118`、#6は`FLW-TSK-120`）。production経路での実証がgatingで未了 |
| 3 | 有限収束性 | **検証計画** | 13.4 全childを`process.run()`監督下へ結線済み（素の`subprocess.run`は0件）。10,000 event／100 MiB規模の負荷実測は未実施 |
| 4 | platform実在性 | **検証計画** | 13.5 probe実装済み。linuxは実観測済み（ext4/tmpfsでSUPPORTED、9pでnetwork拒否）。macos／windowsは実装のみで実走未実施 |
| 5 | 証跡妥当性 | **検証計画** | `FLW-TSK-121`でcoverage manifestを`contract_version: 2`へ上げfixture／productionを関数単位で分離。`FLW-NFR-014`のfixture出口条件を撤回しproduction証跡へ据え直した。実証は公開集合復帰後 |
| 6 | legacy排除 | **検証計画** | 13.6 の旧承認経路は`FLW-TSK-115`で除去済み（参照0件）。宣言／registry検出のblack-box化は公開集合復帰後 |
| 7 | 状態意味保存 | **検証計画** | 13.2の`QUARANTINED`不変条件は`FLW-TSK-119`、marker適格性は`FLW-TSK-120`で実装・検証済み。production経路での実証がgatingで未了 |

**Gate判定への拘束**: 7観点に`実証済み`は依然1件も無い（`FLW-TSK-115`／`116`後も、production既定dispatcherからの到達がgatingで閉じているため）。したがって本設計は
`FLW-CON-008`により、**接続の成立を根拠としたDesign Gate PASSを主張しない**。
本節が求める裁定は「是正の設計方針としての妥当性」であり、`FLW-REV-027`のGate blocking条件
（production既定dispatcher実走、**`target OS` 3種の実観測**、全crash境界、finite timeout）は
実装後の再レビューでのみ解除できる。

**混同への注意**: 2026-08-24に`agent platform` 3者（claude／codex／antigravity）の
confirmationがPASSしたが、**これはGate blocking条件の「実観測」を満たさない**。
confirmationは3者とも同一Linuxホスト上でfixture suiteを実行するものであり、
macOS／Windowsの実観測は依然として未実施である（§13.5）。

## Revision History

- 2.8 (2026-08-24) operation全体deadlineとsnapshot専用出力上限を設計値化し、
  10,000 event条件の収束実測を記録（`FLW-REV-028:GP-002`）
- 2.7 (2026-08-24) 恒真の`semantic_self_test`を撤去し§3.2をprobeの実能力へ書き直す。
  `tmpfs`をallowlistから外し§1.1のdurability前提を明記（`FLW-REV-028:GP-007`）
- 2.6 (2026-08-24) §13.5へprobeの実証義務を追加。symlinkの実証検出、mount局所のcase判定、
  mount point最長一致によるfilesystem種別解決（`FLW-REV-028:GP-006`／`GP-008`）
- 2.5 (2026-08-24) §13.2へ`UNSUPPORTED`行とoperator action義務を追加（`FLW-REV-028:GP-001`）
- 2.4 (2026-08-24) 保証scopeをLinuxへ限定し、case-insensitive環境と対象外platformを
  理由付きで`UNSUPPORTED_FILESYSTEM`へ閉じる。§3.2のsemantic self-test要求と実装の
  乖離を明記（裁定参照: .spec/reports/decision-2026-08-24-linux-only-scope.md。
  `FLW-REV-028:GP-003`／`GP-005`）
- 2.3 (2026-08-24) FLW-REV-027のFAILを受け、`FLW-CON-008`が要求する6表（§13）を追加。
  §4.2のintent／緊急receiptを単一durable recordへ統合し、production未接続・timeout欠落・
  Windows代替component・legacy残存を未実装境界として明示（SI-FLW-084〜090。
  裁定参照: .spec/reports/decision-2026-08-24-flw-rev-027-remediation.md）
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
