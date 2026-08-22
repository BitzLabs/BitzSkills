---
id: FLW-DSN-017
title: "approval-mode 宣言の観測可能な再照合と安全な束縛"
status: draft
version: 1.3
updated: 2026-08-22
owner: codex
implements: FLW-NFR-014
origin: SI-FLW-077, SI-FLW-078, SI-FLW-079
---

# FLW-DSN-017 approval-mode 宣言の観測可能な再照合と安全な束縛

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
hardlink count 1、expected identityを要求する。network filesystem、lock semantics不明、owner/ACL検査不能は
`UNSUPPORTED`とする。counter更新には`FLW-NFR-007`の同一directory temp、file fsync、atomic replace、
directory fsync、再parse・digest検証を適用する。tokenはunsigned 64-bitで、最大値到達、欠損、巻戻り、
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
| `worktree_runtime` | 非追随path walk、HEAD/index/worktree照合、plan固定、再照合、process間lease、result/receipt原因写像 |
| `worktree_capability` | contract v2 payloadにdigestを必須化し、旧形式・未知fieldを拒否 |
| Git | HEAD tree/blobとindex/worktree contentの照合。Git追跡だけを承認とみなさない |
| target lease | canonical targetをprocess間直列化し、fencing tokenとcrash後reconcileを提供 |
| `MutationGuardian` | leaseを保持してGit childを監督し、終了statusをdurable receiptへ確定 |

result/receiptには本文を含めず、`approval_contract_version`、`approval_declaration_state`、
`approval_declaration_digest`、`approval_recheck_phase`、構造化cause、`fencing_token`を記録する。
`BLOCKED`/`STALE`が連続する場合の利用者導線は「宣言をHEADへcommitして再plan」「競合process終了後に
audit/reconcile」「platform非対応ならplan-digest配備へ明示的に戻す」の3分類とする。

### 6. 物理schemaとcanonicalization

capability、binding、lease、counter、receiptはそれぞれ`schema_version`を必須とし、
`additionalProperties: false`、required field、null許容をJSON Schemaで固定する。canonical JSONはUTF-8、
object key辞書順、余分な空白なし、integerはJSON整数、pathはplatform adapterが生成したNFCのcanonical表現、
Git OIDはobject-format名と小文字hexの組にする。file identityはplatform discriminator付きobjectとし、
異platform間で同じfieldへ文字列を詰めない。fencing tokenは`0..2^64-1`とし、型違い・overflowを拒否する。

schema境界タスクではlease、counter、intention、postcondition、receipt、namespace manifestごとに実体JSON
Schemaを作成し、状態別required/nullable制約を固定する。path比較には
`case_sensitivity: sensitive | insensitive` discriminatorを必須化する。各schemaには同じlogical valueが
同一byte列となるcanonical test vectorと、未知field・NFD・case discriminator欠落の拒否vectorを付ける。

#### 6.1 Unicode受理境界

contract v2の公開JSON、永続record、署名payload、digest payloadに含まれる**全string値とobject key**は、
decode直後かつschema検証・署名検証・digest計算より前に`value == NFC(value)`を満たすことを検査する。
一致しないNFDその他の非NFC入力は正規化して受理せず`BLOCKED`にする。これにより異なる入力byte列が
同じ署名対象へ暗黙変換されることを防ぐ。OS/Gitから取得したpathだけはplatform adapterがNFCへ変換して
canonical pathを生成してよいが、そのadapter出力も同じ検査を通す。表示専用messageはcontract payload外とする。

受理vectorはASCII、合成済み日本語、合成済みaccentを含め、拒否vectorは同じ見た目のNFD key/value、
surrogate、NULを含める。拒否後にparser、署名検証器、sentinel writer、promotion判定を呼んではならない。

#### 6.2 platform別file identityの閉じた表現

`file_identity`は次の`oneOf`で固定し、共通の自由形式objectやplatform間field流用を許さない。
大きな識別子をJSON実装の数値精度に依存させないため、OS整数はcanonicalな文字列で保持する。

| platform | 必須field | canonical表現 |
|---|---|---|
| `linux` | `platform`, `device`, `inode`, `link_count` | `device`/`inode`は先頭zeroなしunsigned decimal、`link_count`は整数`1` |
| `macos` | `platform`, `device`, `inode`, `link_count` | Linuxと同形だがdiscriminatorを共有しない |
| `windows` | `platform`, `volume_serial`, `file_id`, `link_count` | serialは先頭zeroなしlowercase hex、file IDは32桁lowercase hex、`link_count`は整数`1` |

各variantは`additionalProperties: false`とし、異platformのfield混在、負数、先頭zero、大文字hex、桁不足、
`link_count != 1`を拒否する。adapterはpath文字列からidentityを推測せず、保持したhandle/FDへのOS照会値から
構築する。取得不能、値域外、open前後のidentity不一致は`UNSUPPORTED`または`BLOCKED`であり、
文字列pathやcontent digestへのfallbackを行わない。

#### 6.3 schemaとruntime codecの双方向整合

schema inventoryは各recordについて`schema_id`、`owner_task`、`activation`、runtimeの`decoder`/`encoder`を
一意に対応付ける。`activation`は`active`または`reserved`の閉集合とする。

| record | owner | 106完了時 |
|---|---|---|
| approval capability v2、minimum-runtime v1、entrypoint inventory/evidence | schema境界 | `active` |
| approval binding v2 | HEAD/index/worktree binding | `reserved` |
| target lease、fencing counter、intention、postcondition、lock namespace v2 | process間lease | `reserved` |
| mutation receipt v2 | runtime統合 | `reserved` |

`active` recordはschemaの`properties`、`required`、parser許可field、serializer出力field、実装型fieldが
完全一致し、valid fixtureを`decode → encode → schema validate → canonical encode`して同一byte列へ戻す。
schemaだけの自己比較は完了証拠にしない。`reserved` recordはschema自体を検証するがcodec不在を欠陥とせず、
producer/consumer登録とstate生成を禁止する。owner taskがcodecと同じ双方向testを追加したcommitでだけ
`active`へ遷移できる。この分離により、schema境界の完了が後続lease実装を待つ循環依存を作らない。

#### 6.4 supported entrypoint inventoryの実体証明

promotion preflightの期待集合と観測値を呼出元が同時に渡すAPIは、論理整合のtest doubleに限定し、
本番のpromotion根拠にしない。本番では配布profileに同梱したclosed policyから期待entrypoint ID集合を読み、
platform adapterがstable launcher、公開CLI、enabled plugin cacheを列挙する。現在の公開CLIは
`<flow-core>/scripts/flow.py`だけであり、`flowlib`直呼出しはinventory対象外とする。Claude Code、Codex、
Antigravityの各plugin cacheは、有効化registryが指す実pathを列挙し、同じ実体を指すaliasはfile identityで
重複排除する。

各実entrypointを副作用なしの`runtime-contract` probeとしてchild process起動し、次のclosed evidenceを得る。

```text
entrypoint_id
entrypoint_kind       # stable-launcher / public-cli / plugin-cache
resolved_file_identity
artifact_sha256       # launcherとimport対象flowlib treeのmanifest digest
runtime_version
contract_versions     # minimum-runtime=1, worktree-state=2
sentinel_aware        # trueのみ受理
probe_exit_code       # 0のみ受理
```

policy期待集合と列挙集合の差、probe未実装・timeout・非zero終了、identity差替え、artifact digest不一致、
baseline未満、`sentinel_aware != true`はpromotionを`UNSUPPORTED`または`BLOCKED`にし、contract v2 stateを
生成しない。testは一時directoryに実entrypoint artifactを配置してprocessを起動し、旧runtime残存、alias、
実行中差替え、欠落cacheの陽性対照を持つ。文字列のversion mappingだけを直接渡すtestは補助testに留める。

### 7. 運用監視とrunbook

cause別`BLOCKED`/`STALE`/`UNSUPPORTED`件数、lock待機時間、quarantine滞留時間、token不連続、
receipt chain検証失敗をSLIとする。1 operation内のtoken不連続、chain failure、quarantine 24時間超過は
即時review対象、同一causeの3回連続停止はrunbook案内対象とする。receiptは`FLW-NFR-011`の保持境界に従い、
改ざん検査とcorrelation keyでplan/result/receiptを接続する。解除はreviewer、根拠digest、旧新token、
postconditionを新receiptへ追記した場合だけ許可する。

receipt/SLI統合タスクは`plugins/bitz-flow/docs/runbooks/m2-worktree-quarantine.md`を成果物とし、audit、
reconcile、quarantine解除の各CLI、一次対応role、reviewer承認経路、通知adapter、24時間超過時のescalationを
固定する。通知adapter未設定でもreceiptと終了codeを失わず、CLIに手動通知先を表示する。

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
- Linux・macOS・Windowsのfile identity正常vectorを受理し、variant間field混在、非canonical整数、
  link count異常、open前後差替えをfail-closedにする。
- active schemaはruntime codecとの双方向round-tripを通し、reserved schemaにはproducerが存在しない。
- 配布policyから得た期待集合と実filesystem/registryから列挙・process probeしたentrypoint集合を照合し、
  caller作成の論理version mappingだけではpromotionできない。
- 別processの同一target競合は最大1processだけがmutationへ進み、process kill後は新fencing tokenと
  receipt reconcileなしに再開しない。
- result/receiptからrecheck phaseと原因を追跡でき、秘密本文やpath外情報を含めない。

## 影響範囲・ロールバック

対象は`worktree_runtime.py`、`worktree_capability.py`、target guard/coordinator、receipt schema、M2 runtime
testsとcapability fixture。配備時点のv1 plan/capabilityは`BLOCKED`として再planする。rollback時にv2の
pending receipt/nonceがある場合は自動でv1へ戻さずquarantineし、人間確認後にreplanする。
M2は未公開のため公開利用者の移行は不要だが、「検証不能なら`BLOCKED`」はrollbackでも維持する。

version切替は二段階にする。第1段階でcommon-dirの保護済みnamespaceへ
`minimum_runtime_version` sentinelと起動時schema gateだけを導入する。sentinelはowner-only regular file、
hardlink count 1、非追随walk、`FLW-NFR-007`のatomic replace/fsyncを適用したversioned JSONとする。

第2段階の前にpromotion barrierを置く。stable launcher、CLI、plugin cacheを含むサポート対象の全起動経路を
inventory化し、各entrypointがsentinel-aware baseline以降であること、pre-baseline entrypointが無効化・撤去
されていることを§6.4の実process probeで確認する。この証明ができない配備は`UNSUPPORTED`としてcontract v2 stateを
生成しない。pre-baseline binaryを利用者が保護境界外から直接持ち込んで実行することは機械的に阻止できず、
サポート対象外の残余リスクである。

promotion後にcontract v2 stateを生成する。一度生成した環境では、sentinel-aware runtimeはv2 reconcileが
pending/quarantine/leaseなしを証明しdowngrade receiptを記録するまで旧version起動を拒否する。旧binaryへ
単純に戻す操作はsupportせず、pre-baseline entrypointを再導入した配備は直ちにsupport外とする。

実装は次の独立境界に分ける: (1) HEAD/index/worktree三者照合reader、(2) capability/schema v2と
minimum-version gateとpromotion preflight、(3) OS lock・namespace manifest・fencing状態機械・
`MutationGuardian`、(4) receipt/SLI/runbook統合。
各段階はfail-closedなfeature flagの背後で検証し、前段がgreenになるまで次段を有効化しない。

## 後続の仕様化

本改訂は`FLW-NFR-013`の既存greenをredにし得るため、同一IDを変更せず後継`FLW-NFR-014`を起票した。
2026-08-22にuserが`SI-FLW-078`の案B、`SI-FLW-079`、`FLW-NFR-014`を承認し、`FLW-NFR-013`を
deprecatedとして後継へ接続した。同日の`FLW-GATE-004`でDesign Gateを通過し、実装タスク再分解へ移る。

## FLW-REV-021 指摘への対応

| 指摘 | 再設計上の処置 |
|---|---|
| SYN-001 | 観測可能なcheckpoint契約、非追随path walk、決定的fault hook、残余TOCTOU明示 |
| SYN-004 | OS lock、durable fencing token、crash後reconcileによるprocess間lease |
| SYN-005 | 非観測履歴を保証対象から外す案Bと、観測点の状態/digest照合 |
| SYN-006 | capability contract v2、必須digest、v1/未知field拒否、replan/rollback規則 |
| SYN-008 | `FLW-FR-006`、`FLW-NFR-007`、`FLW-NFR-012`への派生接続 |

## Revision History

- 1.3 (2026-08-22) NFD拒否境界、platform別file identity、active/reserved codec整合、実entrypoint probeを具体化し再レビューへ戻した
- 1.2 (2026-08-22) promotion barrierとminimum-runtime rollback境界を追加
