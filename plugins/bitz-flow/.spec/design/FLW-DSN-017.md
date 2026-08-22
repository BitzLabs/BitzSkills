---
id: FLW-DSN-017
title: "approval-mode contract v2のSafety Kernelと運用制御面"
status: draft
version: 1.5
updated: 2026-08-22
owner: codex
implements: FLW-NFR-014
origin: SI-FLW-077, SI-FLW-078, SI-FLW-079
---

# FLW-DSN-017 approval-mode contract v2のSafety Kernelと運用制御面

## 背景 / 課題

`approval-mode.json` は signed-capability を必要とする配備意図を、common-dir の鍵 registry から分離する安全境界である。しかし現実装は path の存在と JSON 内容だけを読み、symlink・非通常ファイル・未追跡 file と、plan 作成後の内容差替えを区別しない。そのため、plan 時には強い承認を表示しても apply 時に弱い `plan-digest` へ差し替えられる。

本設計は `FLW-DSN-016` §4 の「宣言と鍵実体の分離」と、`FLW-NFR-007` のfile identity・
原子性、`FLW-NFR-012` のtarget guardを統合する。`FLW-REV-021`のFAILを受け、非観測の中間履歴を
検出済みと主張せず、必須観測点で確認できる承認強度を確実に束縛する設計へ改める。

## 設計判断

### 1. 宣言の信頼状態を閉集合にする

`read_approval_mode_declaration()` は mode 文字列ではなく、次の `ApprovalDeclarationBinding` を返す。検証不能な状態を「宣言なし」と同一視しない。

| 状態 | 判定 | apply 可否 |
|---|---|---|
| `absent` | HEAD・index・worktreeの三者すべてにpath/blobが存在しない | `plan-digest` を許可 |
| `bound` | rootから全componentが非追随、regular file、有効OS principal所有、group/world非書込み、HEAD・index・worktreeのblob一致 | 宣言された mode を許可 |
| `invalid` | component symlink/reparse point、directory、所有・権限不正、未追跡、staged-only、blob不一致、読取競合 | `BLOCKED` |

POSIXではcanonical repository rootのdirectory FDからcomponentごとに`openat`相当と
`O_NOFOLLOW`を用い、Windowsではreparse pointを拒否する同等adapterを用いる。ownerはCLI processの
有効OS principal（POSIX effective UID、Windows process tokenのowner SID）とする。取得不能な場合は
`bound`を推測せず`UNSUPPORTED`または`BLOCKED`にする。

Gitの信頼根はindexだけでなくreview対象のHEAD treeとする。HEADの
`.bitz-flow/approval-mode.json` blob、index blob、worktree content hashが同一の場合だけ`bound`とする。
未追跡またはstaged-only宣言、staged deletion、HEAD/indexにblobがあるworktree削除は配備意図として
受理せず`invalid`にする。open前後のdevice/inode/size/mtimeも比較し、read中の置換を`invalid`にする。

### 2. plan と capability に binding digest を含める

`ApprovalDeclarationBinding` の正規化 payload は次を含む。

```text
repo_root_canonical
git_dir_canonical
repo_root_native_path_digest # 表示pathではなく可逆native component列のdigest
git_dir_native_path_digest   # 同上
repository_identity_digest # canonical git-dir + object-format + initial identity evidence
contract_version      # 2
state                 # absent / bound
mode                  # absent 時は plan-digest
head_tree_oid         # absent 時は null
head_blob_oid         # absent 時は null
index_blob_oid        # absent 時は null、bound時はhead_blob_oidと一致
worktree_content_sha256 # absent 時は null
file_identity         # platform固有の安定identity（absent 時は null）
```

このcanonical payloadのSHA-256を`approval_declaration_digest`とし、`RuntimePlan.snapshot`、
`operation_id`、capability context、receiptへ同じ値を入れる。signed-capability envelopeは
`contract_version: 2`とdigestを必須fieldにする。version 1、field欠落、未知field、digest不一致は
既定値へ補完せず`BLOCKED`にする。M2は未公開なのでv1互換readerは置かない。

要件上の`OperationPlan`は抽象契約名、実装型`RuntimePlan`はそのM2 worktree adapterである。
`repository_identity_digest`は既存repository identity導出器の出力をそのまま用い、root/git-dirの
文字列連結を独自identityとして再実装しない。
`repo_root_canonical`と`git_dir_canonical`は表示・診断用であり、guard key、nonexistence digest、
`operation_id`、capability scopeの安全判定には使わない。安全判定は§6.1の可逆native path表現と
parent directory identityから得たdigestを用いる。

### 3. 再照合点と失敗分類

再照合はplan作成時、approval検証後かつ永続target lease取得直後、各Git child process起動直前の
3段階で行う。`FLW-DSN-016` §4どおりapproval前にleaseを保持しない。テストhookは再照合の前にだけ
置き、最終再照合からchild process起動までに任意callbackを挟まない。

| 観測 | result | 副作用 |
|---|---|---|
| plan 時に `invalid` | `BLOCKED` | 0 |
| apply 時に宣言が読めない／不正 | `BLOCKED` | 0 |
| plan 時の digest と apply 時の digest が異なる | `STALE` | 0 |
| mutation直前の観測でdigestが変わる | `STALE`、receiptをquarantine | 以後 0 |
| 宣言なしが plan 時から継続 | `plan-digest` | 既存どおり |

`STALE`は人間が新しいplanを確認する状態であり、自動再applyしない。`BLOCKED`は配備意図を安全に
観測できない状態である。必須観測点の間に宣言が一時作成・削除され、次の観測前に同一状態へ戻った
履歴は検出済みと主張しない。これはローカルfilesystemで観測不能な履歴を保証対象にしない案Bの境界で、
各観測時点の承認強度低下は引き続きfail-closedに止める。

成功した最終再照合を承認判定の**線形化点**とする。result/receiptへphase、digest、時刻順序を記録し、
保証するのはこの線形化点で観測した状態である。線形化点後のOS preemptionや外部書換えをmutation時点まで
排除したとは報告せず、次の必須観測点で検出する。mutation開始時までの絶対保証はrepo外trust serviceなしに
成立しないためM2対象外とする。

### 4. target guardをprocess間leaseへ拡張する

現行`TargetGuardManager`はprocess内の先行取得検査として残し、その外側にcommon-dir配下の
`bitz-flow-v2/locks/<target-key-sha256>.lock`を用いた非blocking OS lockを置く。複数targetはcanonical
key昇順で全lockを取得し、逆順要求を拒否する。lock取得後、owner-onlyのdurable counterを原子的に
更新して単調増加fencing tokenを発行し、receiptとmutation contextへ記録する。

process crashではOSがlockを解放するが、後続processは新tokenを取得し、既存のnonce/receipt chainを
reconcileして前tokenのpostconditionが確定するまでmutationへ進まない。OS lockまたはdurable tokenを
安全に提供できないplatformでは`UNSUPPORTED`、競合中は副作用なしの`BLOCKED`を返す。

#### 4.1 lock/counter格納域の完全性

`bitz-flow-v2/locks`とcounter/lease recordはcommon-dirからcomponent単位で非追随walkし、owner-only、
expected identityを要求する。hardlink count 1はregular file recordだけへ課し、locks directoryには
§6.2のdirectory identityを使う。network filesystem、lock semantics不明、owner/ACL検査不能は
`UNSUPPORTED`とする。counter更新には`FLW-NFR-007`の同一directory temp、file fsync、atomic replace、
directory fsync、再parse・digest検証を適用する。tokenはunsigned 64-bitのcanonical decimal stringで、
最大値到達、欠損、巻戻り、
receipt chainから再構成した下限未満を`INDETERMINATE`にする。

locks directoryの期待identityは同じ保護境界の`lock-namespace.json`に、schema version、repository
identity、directory file identity、作成時principalを含めてdurableに記録する。coordinatorはcommon-dirから
保持したparent directory handle/FDを起点にmanifestとlocks directoryを開き、取得前後で名前から得たidentityと
manifestの期待identityを照合する。manifest欠損・不一致・名前差替えを自動再作成で修復せず、
`INDETERMINATE`としてnamespace全体をquarantineする。

#### 4.2 fencing状態機械とcommit point

```text
LOCKED
  → TOKEN_DURABLE
  → INTENTION_DURABLE
  → MUTATING
  → POSTCONDITION_DURABLE
  → DONE / QUARANTINED
```

| crash点 | 後続判定 | 後続mutation |
|---|---|---|
| `LOCKED`前後、token未永続 | token未発行として再取得 | 可 |
| `TOKEN_DURABLE`、intentionなし | 副作用0を確認し、取消receipt後に新token | 条件付き可 |
| `INTENTION_DURABLE`、mutation前 | target snapshot一致時だけ`STALE`再plan | 自動不可 |
| `MUTATING`、postcondition未確定 | `INDETERMINATE` / quarantine | 不可 |
| `POSTCONDITION_DURABLE`、DONE未記録 | postconditionとreceipt prefix一致ならDONE補完 | 補完後可 |

状態の正は上書き可能な単一fileではなく、`operations/<operation-id>/events/`配下の
不変phase event列とする。event名は単調なsequence、phase、event digestを含み、各eventは
直前event digest、operation ID、fencing token、target identityを必ず持つ。作成中temp fileの
file fsync、未使用名への一度だけの公開、directory fsyncが成功したeventだけをdurableとし、
確定済みeventの上書き・削除・sequence再利用を禁止する。counterとpromotionのcurrent pointerだけは
保護lock下のatomic replaceを許し、その新値もevent/receiptから照合できなければならない。

復旧はevent列の最長な有効hash chainだけを信頼し、一時file、sequence gap、branchしたchain、
schema不明eventを`INDETERMINATE`とする。これにより、機械と運用者が同じphase列を根拠に
crash位置と次の許容操作を判定する。

各mutation直前にOS lock handle、lease owner、operation ID、最新tokenを同じcoordinator境界で照合する。
Git自体はtokenを解釈しないため、tokenはOS lockの代替ではなくstale writer検出と復旧順序の証拠である。

#### 4.3 Git childのlease継承と監督

標準経路を`MutationGuardian` wrapperへ一本化する。guardianはoperation ID、fencing token、lease handleを
継承し、専用process group/Job Object内でGit childを起動し、終了statusをdurable receiptへ記録するまでleaseを
保持する。Linuxはguardianとprocess group（利用可能ならparent-death signalを補助利用）、macOSはguardianと
明示的lease FD継承、Windowsはguardian、Job Objectのkill-on-close、明示的handle inheritanceを用いる。
coordinatorまたはguardian crash後にGit childの終了とreceiptを証明できない場合、`MUTATING` stateを
`INDETERMINATE`としてquarantineし、後続processはlockを取得できてもmutationへ進まない。

#### 4.4 platform capability matrix

| 能力 | Linux/macOS | Windows | 不成立時 |
|---|---|---|---|
| 非追随walk | dir FD + `openat`/`O_NOFOLLOW`、`fstat` | root-relative handle、reparse point拒否 | `UNSUPPORTED` |
| owner/write権限 | effective UID、mode/ACL | process token SID、DACL write評価 | `BLOCKED` |
| file identity | device+inode+link count | volume serial+file ID+link count | `UNSUPPORTED` |
| process間lock | 検証済みlocal FSの`flock`/`fcntl` adapter | `LockFileEx`+share mode | `UNSUPPORTED` |
| child監督 | MutationGuardian+process group+lease FD（Linuxではparent-death signalを補助利用） | MutationGuardian+Job Object kill-on-close+lease handle | `INDETERMINATE` |

adapterは起動時self-testでsemantic fixtureを通した能力だけをsupportedにする。Linux・macOS・Windowsの通常系で
`UNSUPPORTED` 0件をM2出口条件とし、満たせない場合は人間がscope変更を裁定する。

### 5. 責務分離と監査証跡

| コンポーネント | 責務 |
|---|---|
| `ContractKernel` | canonical JSON、digest、native path、resource identity、schema/codecを決定論的に処理。OS/Git/process副作用は持たない |
| `PlatformEvidenceAdapter` | 非追随walk、identity、owner/ACL、lock、durability、child監督のOS観測とprimitive。ポリシー判定は行わない |
| `MinimumRuntimeController` | sentinelの読み書きと起動時schema gate。promotionやGit mutationは行わない |
| `PromotionController` | 署名baseline、entrypoint inventory/probe、commit直前再照合、v2 active stateとpromotion receiptを所有 |
| `ApprovalBindingReader` | HEAD/index/worktree三者照合とbinding snapshot導出。leaseやmutationは行わない |
| `MutationCoordinator` | plan固定、再照合、target lease、fencing、journal、`MutationGuardian`を統括し、Git mutationを起動できる唯一のcomponent |
| `RecoveryController` | receipt chain検証、crash reconcile、quarantineの照会と署名済み解除裁定記録。Git mutationと自動再開は行わない |
| `OperationsControlPlane` | read-only doctor、promotion/quarantine/receiptの管理CLI、SLI、runbook、通知adapter。上位コンポーネントの公開APIだけを使う |

依存方向は`CLI / Runtime → Promotion / Mutation / Recovery → ContractKernel / PlatformEvidenceAdapter`の
一方向とし、kernel/adapterからorchestratorやCLIへの逆依存を禁止する。
`PromotionController`、`RecoveryController`、`OperationsControlPlane`はGit childを起動できない。
OS adapterの観測失敗をpolicy resultへ写像するのは各controllerであり、adapterが
`BLOCKED`と正常状態を選択しない。

result/receiptには本文を含めず、`approval_contract_version`、`approval_declaration_state`、
`approval_declaration_digest`、`approval_recheck_phase`、構造化cause、`fencing_token`を記録する。
CLIが返す停止resultはこれらに加え、`side_effect_state`（`none` / `confirmed-complete` /
`confirmed-incomplete` / `indeterminate`）、`automatic_recovery_allowed`、`operator_action`、
`operation_id`、`receipt_path`を必須とする。`operator_action`は自由文だけでなく閉じた
action codeと表示文を持ち、危険な再実行を推奨しない。
`BLOCKED`/`STALE`が連続する場合の利用者導線は「宣言をHEADへcommitして再plan」「競合process終了後に
audit/reconcile」「platform非対応ならplan-digest配備へ明示的に戻す」の3分類とする。

### 6. 物理schemaとcanonicalization

capability、binding、platform evidence、support profile、sentinel、promotion、lease、counter、
operation event、receipt、quarantine decisionはそれぞれ`schema_version`を必須とし、
`additionalProperties: false`、required field、null許容をJSON Schemaで固定する。canonical JSONはUTF-8、
object key辞書順、余分な空白なし、通常のbounded integerはJSON整数とする。SHA-256は全recordで
`sha256:` + 64桁lowercase hex、Git OIDはobject-format名と小文字hexの組に固定する。file identityは
resource kindとplatformのdiscriminator付きobjectとし、異platform間でfieldを流用しない。fencing tokenは
`0..18446744073709551615`の先頭zeroなしdecimal stringとし、parserで値域を検査する。

schema境界タスクではlease、counter、operation phase event、receipt、namespace manifestごとに実体JSON
Schemaを作成し、状態別required/nullable制約を固定する。path比較には
`case_sensitivity: sensitive | insensitive` discriminatorを必須化する。各schemaには同じlogical valueが
同一byte列となるcanonical test vectorと、未知field・NFD・case discriminator欠落の拒否vectorを付ける。

#### 6.1 Unicode受理境界

contract v2の公開JSON、永続record、署名payload、digest payloadに含まれる**全string値とobject key**は、
decode直後かつschema検証・署名検証・digest計算より前に`value == NFC(value)`を満たすことを検査する。
一致しないNFDその他の非NFC入力は正規化して受理せず`BLOCKED`にする。これにより異なる入力byte列が
同じ署名対象へ暗黙変換されることを防ぐ。表示専用messageはcontract payload外とする。

OS/Git由来pathはこの規則の例外として文字列へ正規化せず、各componentのnative nameを可逆なASCII objectへ
符号化する。POSIXはdirfd基準で得たbyte列をunpadded base64url、Windowsはroot-relative handleで得たUTF-16LE
code unit列を同形式で保持する。path payloadは次を必須とする。

```text
platform               # linux / macos / windows
native_encoding        # posix-bytes / windows-utf16le
components_base64url   # rootからの長さ付きcomponent列。`.` / `..` / 空componentは禁止
case_sensitivity       # sensitive / insensitive
normalization_semantics # byte-exact / volume-reported
parent_directory_identity
```

guard key、nonexistence digest、operation identity、capability scopeはこのobjectのcanonical digestを使う。
NFC/NFD、case variant、別mount aliasを文字列正規化で同一視しない。macOS/Windowsでvolume semanticsを安全に
取得できない場合と、利用者入力をnative componentへ一意に対応付けられない場合は`UNSUPPORTED`または
`BLOCKED`とする。不在targetはparent directory identityと末尾native componentを必ず含める。

受理vectorはASCII、合成済み日本語、合成済みaccentを含め、拒否vectorは同じ見た目のNFD key/value、
surrogate、NULを含める。native path vectorはNFC/NFDが同居するdirectory、両方不在、片方だけ存在するcreateを
含め、scope digestが衝突しないことを確認する。拒否後にparser、署名検証器、sentinel writer、promotion判定を
呼んではならない。

#### 6.2 platform別file identityの閉じた表現

identityは`regular_file_identity`と`directory_identity`を別の`oneOf`へ分離し、共通の自由形式objectや
platform間field流用を許さない。大きなOS整数はJSONの数値精度に依存させずcanonical stringで保持する。

| resource kind | platform | 必須field | canonical表現 |
|---|---|---|---|
| `regular-file` | `linux` / `macos` | `kind`, `platform`, `device`, `inode`, `link_count` | device/inodeは`0`または先頭zeroなしuint64 decimal、link_countはdecimal string `1` |
| `directory` | `linux` / `macos` | `kind`, `platform`, `device`, `inode` | device/inodeは同上。directory link countは子directory作成で変動するためidentityへ含めない |
| `regular-file` | `windows` | `kind`, `platform`, `volume_serial`, `file_id`, `link_count` | serialは`0`または1〜16桁lowercase hex、file IDは32桁lowercase hex、link_countはdecimal string `1` |
| `directory` | `windows` | `kind`, `platform`, `volume_serial`, `file_id` | serial/file IDは同上。link countはidentityへ含めない |

各variantは`additionalProperties: false`とし、異resource/platform field混在、uint64値域外、負数、先頭zero、
大文字hex、桁不足、regular fileの`link_count != "1"`を拒否する。adapterはpath文字列からidentityを推測せず、
保持したhandle/FDへのOS照会値から構築する。resource kindは同じhandleへの`fstat`相当で確認する。
取得不能、open前後のidentity/kind不一致は`UNSUPPORTED`または`BLOCKED`であり、pathやcontent digestへfallbackしない。

#### 6.3 schemaとruntime codecの双方向整合

schema inventoryは単一共有fileではなく`schemas/worktree-v2/activation/<schema-id>.json`のowner別manifest群とする。
各manifestは`schema_id`、`owner_task`、`activation`、runtimeの`decoder`/`encoder`を一意に対応付ける。
中央loaderはschema ID重複、owner不一致、未知activationを拒否する。`activation`は`active`または`reserved`の
閉集合とし、各taskは自分が所有するmanifestだけを変更するため、並行する後続taskが共有inventoryで競合しない。

| record | owner task | owner task完了時 |
|---|---|---|
| approval capability v2、共通identity/path/digest定義 | FLW-TSK-106 | `active` |
| platform evidence、support profile | FLW-TSK-111 | `active` |
| minimum-runtime v1 | FLW-TSK-112 | `active` |
| entrypoint policy/evidence、promotion state/receipt | FLW-TSK-113 | `active` |
| approval binding v2 | FLW-TSK-107 | `active` |
| target lease、fencing counter、operation phase event、lock namespace v2 | FLW-TSK-108 | `active` |
| mutation receipt v2 | FLW-TSK-109 | `active` |
| quarantine release decision/receipt extension | FLW-TSK-110 | `active` |

`active` recordはschemaの`properties`、`required`、parser許可field、serializer出力field、実装型fieldが
完全一致し、valid fixtureを`decode → encode → schema validate → canonical encode`して同一byte列へ戻す。
schemaだけの自己比較は完了証拠にしない。`reserved` recordはschema自体を検証するがcodec不在を欠陥とせず、
producer/consumer登録とstate生成を禁止する。owner taskがcodecと同じ双方向testを追加したcommitでだけ
自分のactivation manifestを`active`へ遷移できる。owner taskのboundaryは担当schema、activation manifest、
codec、round-trip testを同じrollback単位に含める。この分離により、schema境界の完了が後続lease実装を待つ
循環依存を作らず、後続taskもboundary違反なしにproducerを有効化できる。

#### 6.4 supported entrypoint inventoryの実体証明

promotion preflightの期待集合と観測値を呼出元が同時に渡すAPIは、論理整合のtest doubleに限定し、
本番のpromotion根拠にしない。本番では配布profileに同梱した署名対象のclosed baseline manifestから
entrypoint ID、kind、runtime SemVer、許可artifact digest、contract versionを読み、platform adapterが
stable launcher、公開CLI、enabled plugin cacheを列挙する。manifestはschema versionと配布versionを持ち、
plugin releaseと同じreview・署名境界でのみ更新する。現在の公開CLIは
`<flow-core>/scripts/flow.py`だけであり、`flowlib`直呼出しはinventory対象外とする。Claude Code、Codex、
Antigravityの各plugin cacheは、有効化registryが指す実pathを列挙し、同じ実体を指すaliasはfile identityで
重複排除する。ただし期待logical IDとの対応は保持し、aliasによって期待entrypointの欠落を隠さない。

親processはentrypointとimport対象`flowlib` treeを保持handleから列挙し、canonical manifest digestを独立計算する。
baseline不一致・identity不一致・未知artifactはchildとして**起動せず**`BLOCKED`にする。artifact一致後だけ、
機能証拠を得るために実entrypointを`runtime-contract` probeとして起動する。childの自己申告値は親計算digest、
実行handle identity、baseline値、親が生成した単回challenge nonceと一致した場合だけ証拠にする。

各実entrypointを副作用なしの`runtime-contract` probeとしてchild process起動し、次のclosed evidenceを得る。

```text
entrypoint_id
entrypoint_kind       # stable-launcher / public-cli / plugin-cache
resolved_file_identity
artifact_sha256       # 親processが計算したlauncherとimport対象flowlib treeのmanifest digest
runtime_version
contract_versions     # minimum-runtime=1, worktree-state=2
sentinel_aware        # trueのみ受理
probe_exit_code       # 0のみ受理
challenge_digest      # 親の単回nonceへ束縛した応答
registry_generation
```

probeは親が検証済みartifactだけを、固定argv、空のrepository外cwd、allowlist environment、credentialなし、
network endpoint引数なし、repository/common-dir read-only、不要FD/handle非継承で起動する。POSIXは専用process group、
WindowsはJob Objectを使い、monotonic 30秒timeout、2秒のgraceful終了猶予後にprocess treeを強制終了する。
stdoutは64KiBのclosed JSON、stderrは8KiBのsanitized診断を上限とし、超過・timeout・tree終了未確認は
`INDETERMINATE`としてevidenceを残す。検証済みartifactをこの境界で起動できないplatformは`UNSUPPORTED`とする。

runtime versionはSemVer 2.0.0の`major.minor.patch`だけをpromotion比較へ受理する。leading zero、component欠落、
prerelease、build metadataは配布baselineでは拒否し、開発fixtureだけ別profileへ分離する。

列挙開始時にenabled registry generationを取得し、probe完了後、contract v2 stateのdurability commit直前に
同じregistry generation、全entrypoint identity、親計算artifact digestを再照合する。差異は`STALE`としてstateを
生成しない。成功した最終再照合とv2 stateのfile fsync・atomic replace・directory fsyncをpromotionの線形化順序とし、
receiptへbaseline digest、registry generation、entrypoint evidence digest、commit時刻順序を記録する。

policy期待集合と列挙集合の差、probe未実装・timeout・非zero終了、identity差替え、artifact digest不一致、
baseline未満、`sentinel_aware != true`はpromotionを`UNSUPPORTED`、`BLOCKED`、`STALE`、`INDETERMINATE`の
該当分類で停止し、contract v2 stateを生成しない。testは一時directoryに実artifactを配置し、旧runtime残存、
alias、実行中差替え、registry generation変化、欠落cache、hang、出力超過、副作用canaryの陽性対照を持つ。
文字列のversion mappingだけを直接渡すtestは補助testに留める。

### 7. 運用control planeとrunbook

cause別`BLOCKED`/`STALE`/`UNSUPPORTED`件数、lock待機時間、quarantine滞留時間、token不連続、
receipt chain検証失敗をSLIとする。1 operation内のtoken不連続、chain failure、quarantine 24時間超過は
即時review対象、同一causeの3回連続停止はrunbook案内対象とする。receiptは`FLW-NFR-011`の保持境界に従い、
改ざん検査とcorrelation keyでplan/result/receiptを接続する。解除はreviewer、根拠digest、旧新token、
postconditionを新receiptへ追記した場合だけ許可する。

quarantine解除は通常operationでも`NEXT`でもなく、reviewer裁定済み証拠をcontrol-plane receiptへ記録する
管理経路`quarantine-release-record`とする。この経路はGit childを起動せず、通常mutationを自動再開しない。
入力はschema version、repository/target identity、quarantined chain head、expected fencing token、検証済み
postcondition digest、reviewer role付きkey ID、decision digest、単回nonce、署名を持つclosed recordとする。
reviewer keyはtrusted registryの`quarantine-reviewer` roleだけを許可し、実行process自身の未登録keyを受理しない。

管理経路も同じcanonical targetのOS lockを取得し、新fencing token発行、chain head・旧token・postcondition再照合、
release receiptを不変eventとしてfile fsync・一度だけの公開・directory fsyncで確定する。chain変化は`STALE`、postconditionやchild終了を
確定できない場合は`INDETERMINATE`として解除しない。成功後も次のwriteは新しいplanと通常承認を必須とする。
これによりreviewer裁定を機械的に記録できるが、quarantineからGit変更へ直接遷移するwrite operationは追加しない。

receipt/SLI統合タスクは`plugins/bitz-flow/docs/runbooks/m2-worktree-quarantine.md`を成果物とし、audit、
reconcile、`quarantine-release-record`管理CLI、一次対応role、reviewer承認経路、通知adapter、24時間超過時の
escalationを固定する。通知adapter未設定でもreceiptと終了codeを失わず、CLIに手動通知先を表示する。

#### 7.1 運用CLIの公開境界

運用者が内部fileを直接編集しなくても判定できるよう、次の管理APIを公開契約とする。

```text
flow.py worktree doctor --json
flow.py worktree promotion check --json
flow.py worktree promotion apply
flow.py worktree quarantine list
flow.py worktree quarantine show <operation-id>
flow.py worktree quarantine reconcile <operation-id>
flow.py worktree quarantine release-record <decision-file>
flow.py worktree receipt verify <operation-id>
```

`doctor`、`promotion check`、`quarantine list/show`、`receipt verify`はread-onlyで、lock、counter、
sentinel、journal、receiptを変更しない。`reconcile`は最長有効event chainと実postconditionから
証明可能な補完だけを行い、`indeterminate`を操作者の推測で確定状態へ変更しない。
全commandは人間表示と同じclosed resultのJSON出力を持ち、終了codeと`cause_code`の対応を固定する。

#### 7.2 reviewer keyのライフサイクル

trusted registryはpublic key、role、key ID、generation、有効/失効状態を持ち、registry digestを
release decisionとreceiptへ束縛する。bitz-flow runtimeはregistryをread-only検証し、private keyの
生成・保管・出力、reviewerの自己登録、失効keyの復活を行わない。登録・rotation・失効は
配布/導入管理者の保護された経路で行い、紛失時の署名省略や緊急bypassを設けない。
registry generationがdecision作成後に変わった場合は`STALE`とし、新registry下でdecisionを作り直す。

#### 7.3 support profile、保持、容量

各配布profileはOS、filesystem/volume semantics、lock/durability adapter、probe能力を列挙した
署名対象`support-profile.json`を持つ。起動時self-testの成功だけで未登録filesystemを
自動的にsupportedへ格上げず、profileと実観測の両方が一致した場合だけ通常系に入れる。
network filesystem、未登録volume、durability semantics不明は理由付き`UNSUPPORTED_FILESYSTEM`とする。
M2のLinux/macOS/Windows通常系0件は、qualificationで確定したsupport profileごとに判定する。

`QUARANTINED`、`INDETERMINATE`、active operationのjournal/receiptは自動削除しない。`DONE`は
監査保持期間と上限を配布profileで宣言し、archive先の完全性を検証したarchive receiptなしに
原本を削除しない。上限迫近はwrite失敗後ではなくSLIと`doctor`で事前に通知する。

## 代替案と却下理由

- common-dir に「最高到達モード」を保存する案は、registry と同じ書込み主体が marker も削除でき、初期化・移設の運用負担も増えるため採らない。
- 非観測の一時作成・削除までcommon-dir世代台帳で保証する案Aは、同じ書込み主体が台帳も変更でき、
  repo外trust serviceを新設しなければ成立しないためM2では採らない。
- 宣言を毎回読み直すだけの案は、plan 時に人間が確認した内容との結び付きを作れず、強度低下を防げないため採らない。
- symlink を realpath で許可する案は、解決後に置換される TOCTOU と repository 外参照を正当化するため採らない。
- 全配備で signed-capability を強制する案は、宣言なしの既存 `plan-digest` 配備を互換なく停止するため採らない。

## 検証設計

- `bound` の signed-capability と `absent` の plan-digest が既存どおり plan/apply できる。
- parent component symlink/reparse point、directory、未追跡、staged-only、HEAD/index/worktree不一致、
  所有・権限不正はplan段階で`BLOCKED`。
- hookをplan後、approval後、各mutation前へ決定的に置き、内容変更、削除、新規作成、inode置換を
  `STALE`/`BLOCKED`とし、その再照合点以後のGit副作用0件を確認する。
- contract v1、digest欠落・改変、未知field、plan-digest/signed-capability相互転用を拒否する。
- public/永続contractのNFD key/valueをdecode境界で拒否し、暗黙NFC変換後の署名・digest計算へ進まない。
- NFC/NFD native nameが同居するLinux directoryで別scopeを導出し、不在targetもparent identityと末尾componentで
  一意に束縛する。
- Linux・macOS・Windowsのfile identity正常vectorを受理し、variant間field混在、非canonical整数、
  regular fileのlink count異常、file/directory kind混同、open前後差替えをfail-closedにする。
- active schemaはruntime codecとの双方向round-tripを通し、reserved schemaにはproducerが存在しない。
- 配布policyから得た期待集合と実filesystem/registryから列挙・process probeしたentrypoint集合を照合し、
  caller作成の論理version mappingだけではpromotionできない。未知artifactは起動せず、trusted artifactのhang、
  出力超過、registry generation変化、副作用canaryを停止する。
- 2^53境界と2^64-1のfencing tokenをcross-language fixtureで同一canonical byteへし、overflowを拒否する。
- 並行するrelease記録、chain head変化、token差異、postcondition不確定を解除せず、成功後も新planを要求する。
- 別processの同一target競合は最大1processだけがmutationへ進み、process kill後は新fencing tokenと
  receipt reconcileなしに再開しない。
- result/receiptからrecheck phaseと原因を追跡でき、秘密本文やpath外情報を含めない。
- operation journalの各crash pointで最長有効chainから同じphaseと復旧可否を導出し、
  event改変、sequence gap、chain branch、一時file残存をfail-closedにする。
- `doctor`と各read-only管理commandの実行前後でstate digestが変わらず、停止resultに
  cause、side-effect state、自動復旧可否、次action、receipt参照が欠落しない。
- reviewer keyの未登録・失効・role不一致・registry generation変化を解除せず、private keyや
  署名対象の秘密値を診断出力へ含めない。
- audit-onlyからdefault-onまでの各展開phaseで許容されたwriteだけが発生し、
  support profile外filesystemと保持容量不足をmutation前に操作可能な原因として返す。

## 影響範囲・ロールバック

対象はcontract kernel、platform evidence adapter、minimum-runtime controller、promotion controller、
approval binding reader、mutation coordinator、recovery controller、operations control plane、schema activation manifest、
M2 runtime testsとfault fixture。配備時点のv1 plan/capabilityは`BLOCKED`として再planする。rollback時にv2の
pending receipt/nonceがある場合は自動でv1へ戻さずquarantineし、人間確認後にreplanする。
M2は未公開のため公開利用者の移行は不要だが、「検証不能なら`BLOCKED`」はrollbackでも維持する。

version切替は機械状態と運用展開を分け、次の4 phaseで行う。

1. `audit-only`: doctor、support profile照合、entrypoint inventory、path/identity検証だけを行い、sentinel、v2 state、journalを書かない。
2. `sentinel-ready`: common-dirの保護済みnamespaceへ`minimum_runtime_version` sentinelと起動時schema gateだけを導入し、v2 mutationは無効のままにする。
3. `canary`: 明示したrepository/targetだけをpromotionし、receipt、quarantine、reconcile、通知の運用証跡を確認する。
4. `default-on`: canaryの出口条件を満たしたsupport profileでだけv2を既定化する。

sentinelはowner-only regular file、hardlink count 1、非追随walk、`FLW-NFR-007`のatomic replace/fsyncを
適用したversioned JSONとする。promotion barrierはstable launcher、CLI、plugin cacheを含む
サポート対象の全起動経路をinventory化し、各entrypointがsentinel-aware baseline以降であること、
pre-baseline entrypointが無効化・撤去されていることを§6.4の実process probeで確認する。
この証明ができない配備は`UNSUPPORTED`としてcontract v2 stateを生成しない。
pre-baseline binaryを利用者が保護境界外から直接持ち込んで実行することは機械的に阻止できず、
サポート対象外の残余リスクである。

promotion後にcontract v2 stateを生成する。一度生成した環境では、sentinel-aware runtimeはv2 reconcileが
pending/quarantine/leaseなしを証明しdowngrade receiptを記録するまで旧version起動を拒否する。旧binaryへ
単純に戻す操作はsupportせず、pre-baseline entrypointを再導入した配備は直ちにsupport外とする。

実装は次の独立境界に分ける: (1) 純粋なcontract kernel、(2) policyを持たないplatform evidence adapter、
(3) minimum-runtime sentinel、(4) promotion controller、(5) HEAD/index/worktree三者照合reader、
(6) lease/journal/guardian、(7) mutation runtime結線、(8) recovery controller、(9) operations control plane/SLI/runbook。
各段階はfail-closedなfeature flagの背後で検証し、前段がgreenになるまで次段を有効化しない。

## 後続の仕様化

本改訂は`FLW-NFR-013`の既存greenをredにし得るため、同一IDを変更せず後継`FLW-NFR-014`を起票した。
2026-08-22にuserが`SI-FLW-078`の案B、`SI-FLW-079`、`FLW-NFR-014`を承認し、`FLW-NFR-013`を
deprecatedとして後継へ接続した。同日の`FLW-GATE-004`でDesign Gateを通過し、実装タスク再分解へ移る。
2026-08-22のその後、userは正式再レビュー前の自己検討としてSafety KernelとOperations Control Planeの
統合案およびtask分割を承認した。v1.5は旧Gateの対象後に追加した設計変更であるため、`FLW-GATE-004`の通過を
v1.5の承認に流用せず、独立再レビューと新しいDesign Gate裁定が完了するまで実装を再開しない。

## FLW-REV-021 指摘への対応

| 指摘 | 再設計上の処置 |
|---|---|
| SYN-001 | 観測可能なcheckpoint契約、非追随path walk、決定的fault hook、残余TOCTOU明示 |
| SYN-004 | OS lock、durable fencing token、crash後reconcileによるprocess間lease |
| SYN-005 | 非観測履歴を保証対象から外す案Bと、観測点の状態/digest照合 |
| SYN-006 | capability contract v2、必須digest、v1/未知field拒否、replan/rollback規則 |
| SYN-008 | `FLW-FR-006`、`FLW-NFR-007`、`FLW-NFR-012`への派生接続 |

## Revision History

- 1.5 (2026-08-22) Safety KernelとOperations Control Planeを分離し、不変operation journal、運用CLI、reviewer key lifecycle、support/retention profile、4段階rollout、責務別task境界を追加
- 1.4 (2026-08-22) FLW-REV-023のP1〜P3を反映し、native path、identity kind、schema activation所有権、trusted promotion、quarantine管理経路、token/digest/SemVer契約を確定
- 1.3 (2026-08-22) NFD拒否境界、platform別file identity、active/reserved codec整合、実entrypoint probeを具体化し再レビューへ戻した
- 1.2 (2026-08-22) promotion barrierとminimum-runtime rollback境界を追加
