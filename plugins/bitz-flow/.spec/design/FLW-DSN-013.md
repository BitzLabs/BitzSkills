---
id: FLW-DSN-013
title: "Forward Recovery・承認・I/O安全設計"
status: active
version: 1.4
updated: 2026-08-11
owner: hide
implements: FLW-FR-013, FLW-NFR-008, FLW-NFR-003, FLW-NFR-004, FLW-NFR-005, FLW-NFR-006, FLW-NFR-007, FLW-NFR-012, FLW-CON-002, FLW-CON-004, FLW-CON-005
origin: FLW-REV-002
---

# FLW-DSN-013 Forward Recovery・承認・I/O安全設計

## 基本方針

複数のGit/GitHub状態を自動補償で巻き戻さず、確認できた副作用を保全して前進再開する。
汎用的な補償・自動再実行journalは持たず、operation固有marker、digest、ref、SHA、URLから状態を再構成する。
ただしM1 Git writeでは、未確定な副作用を重複実行しないためのdurable intent／CAS receipt hash-chainを
安全記録として持つ。これは補償やblind retryを駆動するjournalではなく、reconcileと人間停止の根拠である。

## 終了状態

| code | 意味 | 次の動作 |
|---|---|---|
| `DONE` | postconditionを確認済み | 次段階へ進む |
| `PARTIAL` | 完了段階と未完了段階を確認済み | 完了済みを再実行せず前進 |
| `INDETERMINATE` | 副作用の成否を一意に判定できない | reconcileのみ許可 |
| `STALE` | planの前提が変化 | planを破棄して再取得 |
| `BLOCKED` | policy/証跡不足 | 人間介入または不足解消 |

`INDETERMINATE`はexit 9とし、raw command fallbackを案内しない。

## Recovery Matrix

| ID | scenario | 照合 | forward recovery |
|---|---|---|---|
| `REC-FETCH` | fetch応答喪失 | remote ref/FETCH_HEAD | expected refならDONE、違えばSTALE |
| `REC-STAGE` | stage応答喪失 | index tree/path set | plan digest一致ならDONE |
| `REC-COMMIT` | commit応答喪失 | plan時HEAD、予定commit OID、expected ref、operation intent/CAS receipt | tree、parent、message、author条件からcommit objectを先に作り予定OIDを確定する。CAS前にoperation ID、旧OID、予定OIDをdurable intentへ記録し、refを単一CASで更新したwriterが同じrecordへCAS結果と前後OIDを追記する。receiptとrefを復元できる場合だけDONE。intentだけ、receipt欠落、refだけ予定OIDならINDETERMINATE |
| `REC-SYNC` | sync応答喪失 | branch/upstream/dirty | expected upstreamへff一致ならDONE |
| `REC-PUSH` | push応答喪失 | remote branch SHA | expected HEADならDONE |
| `REC-REMOTE-DELETE` | remote branch削除応答喪失 | remote refを全page再照会 | 不存在ならDONE、expected SHA残存ならBLOCKEDとして新snapshotのplanと再承認を要求、別SHA存在ならSTALE |
| `REC-WORKTREE-CREATE` | worktree create/resume応答喪失 | worktree list/path/branch/HEAD/common-dir | 全一致ならDONE、一部一致はBLOCKED |
| `REC-WORKTREE-FINISH` | worktree finish応答喪失またはworktree remove後branch削除失敗 | worktree list/local ref | 消えた段階をcompleted_stepsへ入れ、残存branchだけ再開 |
| `REC-WORKTREE-DISCARD` | worktree discard応答喪失 | manifest target/worktree list/ref | 列挙targetだけ不存在ならDONE、未知残存はBLOCKED |
| `REC-PR-PUBLISH` | PR作成応答喪失またはpush成功・PR作成失敗 | remote SHA + marker付きopen PRを全page照会 | head/marker一致が1件ならURLを復元してDONE、0件かつremote SHA一致なら作成から再開、複数ならBLOCKED |
| `REC-ISSUE-PUBLISH` | Issue作成成功・結果喪失 | idempotency markerを全page検索 | 1件ならURLを復元してDONE、0件なら再作成、複数ならBLOCKED |
| `REC-ISSUE-LINK` | Issue作成成功・spec URL未記録 | marker + sdd側期待URL | reconcile-link planを返し、`.spec`は変更しない |
| `REC-ISSUE-COMMENT` | comment応答喪失 | comment markerを全page検索 | 1件ならDONE、0件なら再作成、複数ならBLOCKED |
| `REC-ISSUE-EDIT` | Issue edit応答喪失 | updatedAt/body/label digest | expected digest一致ならDONE |
| `REC-ISSUE-CLOSE` | Issue close応答喪失 | Issue state/updatedAt | CLOSEDならDONE、更新競合はSTALE |
| `REC-PR-READY` | PR ready応答喪失 | draft/head/check/review | draft=falseかつhead一致ならDONE |
| `REC-PR-MERGE` | merge応答喪失 | PR state/head/merge commit | MERGEDかつplanned head一致ならDONE、head進行ならSTALE |
| `REC-CHANGELOG-APPLY` | CHANGELOG apply応答喪失 | path identity/file digest | expected digestならDONE、plan時の旧digestならSTALEとして再plan、どちらでもなければINDETERMINATE |
| `REC-TAG-CREATE` | local tag作成応答喪失 | local annotated tag target | expected target一致ならDONE、不存在なら再作成、別targetならBLOCKED |
| `REC-TAG-PUSH` | tag push応答喪失 | local/remote tag target | remote expected targetならDONE、不存在かつlocal一致ならpushから再開、別targetならBLOCKED |
| `REC-RELEASE-DRAFT` | release draft応答喪失またはremote tag後draft失敗 | tag target + marker付きdraft + notes digestを全page照会 | 1件一致ならURLを復元してDONE、0件かつtag一致ならdraftから再開、複数/不一致はBLOCKED |
| `REC-RELEASE-PUBLISH` | publish成功・post-check失敗 | tag/release state/URL/target | publishedかつexpected targetならDONE。不一致時は再照会のみで自動削除・上書きしない |

照合対象がpaginationや権限不足で全件確認できない場合は`INDETERMINATE`にする。

## idempotency marker

GitHubで重複し得るcreate/comment操作は次の固定markerをbodyへ含める。

```text
<!-- bitz-flow:operation=<idempotency_id> -->
```

- Issue/PR/releaseは本文末尾、commentはcomment末尾へ1つだけ置く。
- markerにrepo path、actor、credential、時刻を含めない。
- editはmarkerを保存し、複数markerを検出したら`BLOCKED`。
- Git commitへ専用trailerは追加せず、parent/tree/message digestで照合する。
- markerはretry識別子であり分散lockではない。同時実行の排他はFLW-DSN-012の
  `concurrency_key`とsingle coordinator前提で扱う。

## 人間承認

1. CLIはplanを返し`APPROVAL_REQUIRED`で停止する。
2. SKILL.mdは対象、effects、不可逆性を人間へ提示し、明示応答までapplyしない。
3. `--confirm`はoperation ID一致だけを検査する。
4. resultの`approval`は`source: external`と任意referenceを記録するが、本人性を主張しない。
5. 明示応答を提示できない実行環境では、SKILL／オーケストレーション層が
   `explicit-human` operationのapplyを呼び出さず、未承認として停止する。

platform hookや独自承認serviceは実装しない。

### 承認の残余リスク

`approval-ref`は監査用の自己申告で、CLIは人間turnとエージェントturnを識別できない。
したがって`explicit-human`はCLIが認証・強制するcapabilityではなく、SKILL／
オーケストレーション層の前提統制とする。CLIが機械的に強制するのはplan鮮度、
operation ID、preconditions、effects上限までであり、applyを呼ぶ権限の付与はhostと利用者の責任とする。
信頼できる承認経路がない環境では、SKILLはapplyを呼ばず「この環境では人間承認を確認できない」
と報告する。`--approval-ref`の有無だけでapply可否を変えない。

3platform evalは「人間応答前apply 0件」を独立oracleにし、応答文からoperation IDをエージェントが
自動転記しただけのcaseを失敗にする。この統制は善意のエージェント運用を検証するもので、
CLIを直接呼べる悪意ある／規律外のcallerへの認可境界ではないことをthreat modelへ残す。

## process runner

- commandはargument array、`shell=False`。
- operation timeoutとは別にaction全体deadlineを持つ。readは1〜300秒、writeは10〜300秒。
- write deadlineはexecution最大60%、termination grace最大10%（1〜5秒）、
  reconciliation reserve最低30%（3秒以上）へ分割し、executionがreserveを消費しない。
- stdout/stderrはoperation別byte上限までmemoryへ読み、超過時はprocessを終了して`UNAVAILABLE`。
- 前項の`UNAVAILABLE`はreadの最終codeに限る。writeの出力上限超過は観測causeとして保持しつつ、
  必ずpostcondition/reconcileで最終codeを決める。一意に収束すれば`DONE` / `PARTIAL` / `STALE`、
  照合不能なら`INDETERMINATE`としてmutationを閉じ、再applyを許可しない。
- timeout時はprocess groupへterminate、短い猶予後kill、必ずwaitする。
- 終了後は必ずoperation別postconditionを照会する。
- POSIXは新規session + process group signal、WindowsはPython `ctypes`のJob Objectでprocess treeを
  所有・終了する。安全なtree収束を提供できないplatformではwriteを`UNSUPPORTED`。
- reconciliation reserve内のread-only照会は最大2回まで。2回ともtimeout/UNAVAILABLEなら
  `INDETERMINATE`でmutationを閉じ、再applyを許可しない。
- 全writeはlock保持中かつmutation前に、repo identity、operation family、canonical target、operation ID、
  snapshot、expected effect、evidence digestを持つowner-onlyの`pending` intention/quarantine recordを
  durable化し、flush/digest検証後だけ副作用を開始する。DONEまたは副作用不成立を証明できた場合だけ
  同じlock内で解除する。crash、UNKNOWN、receipt欠落、reconcile失敗ではpendingを保持し、人間が
  reconcile証跡と解除理由を記録するまで同targetのwriteを`BLOCKED`にする。process再起動、別process、
  result喪失後も保持し、副作用前crash、CAS直後crash、reconcile中crashをfault fixtureへ含める。
- pending intentionのcheck-and-createにはfamily別lockを使わない。全writeはfamily別lockより先に
  `repo identity × canonical mutation target`のtarget guardを取得し、pending検査・作成・mutation・
  reconcile・解除まで保持する。複数targetはcanonical key昇順で全guardを取得しdeadlockを防ぐ。
- read-only network操作だけ、rate limit/一時障害に対して上限回数・総deadline内のbackoffを許可する。
- writeは応答エラーだけを根拠にblind retryせず、必ずreconcileを先に行う。
- exception、traceback、resultへraw stdout/stderrを連結しない。
- causeは許可語彙、command名、stage、exit categoryだけを返す。

## file I/O

- body/notes/commit messageの一時ファイルはowner-only相当で作成する。
- subprocessがstdinを受けられる操作はfileを作らずstdinを優先する。
- 永続file更新前に`lstat`でdevice/inode/owner/mode/link count/digestを記録し、symlink、hardlink、
  repo境界外parent、所有者変化を`BLOCKED`にする。
- 同一directoryへ排他的owner-only tempを作り、write、flush、file fsync、parse/digest検証を行う。
- replace直前に原本identityとdigestを再照会し、一致時だけatomic replaceする。
- replace後にparent directoryをfsyncし、最終fileを再parseする。
- Windowsは`ReplaceFileW`またはwrite-through相当を`ctypes`で利用し、原子性・durabilityを
  capability検証できないfilesystemでは永続file writeを`UNSUPPORTED`。
- 元fileのmode、改行形式、末尾改行を保持する。
- atomic replaceはpublication point、replace後のparent directory durability同期と最終fileの
  parse/digest検証完了をdurability commit pointとする。
- durability commit point前（replace後・directory同期前を含む）のcrashではplan時digestの完全な
  旧版またはexpected digestの完全な新版、commit point後では完全な新版が公開pathに存在し、
  いずれも部分内容を許容しない。
- 再起動時にexpected digestなら`DONE`、plan時の旧digestなら`STALE`として新しいplanを要求し、
  どちらでもなければ`INDETERMINATE`として後続mutationを停止する。
- temp pathをresultへ公開しない。
- cleanup失敗はwarningとし、秘密本文をwarningへ含めない。

## 代替案

- 自動rollback: remote writeの補償自体が新しい破壊操作になるため不採用。
- 内部SQLite journal:外部状態との三重管理になるため不採用。
- raw stderr保存: token・credential漏洩リスクのため不採用。

## 検証

各matrix行について「副作用直前」「副作用直後」「post-check中」のfault fixtureを作る。
重複副作用0、誤補償0、INDETERMINATEからmutation継続0を必須とする。
各write operationはRecovery Matrixの対応行IDをoperation schemaへ必須で持ち、対応行がない
operationはapply handlerを登録できない機械検査にする。

reconcileは1actionにつき最大2回または30秒の短い方で打ち切る。未収束時は人間メンテナへ
target、preconditions、effects、completed/remaining steps、evidence digestを提示し、
同一targetへの後続mutationを禁止する。
