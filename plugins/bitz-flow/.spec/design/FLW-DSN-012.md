---
id: FLW-DSN-012
title: "Operation Contract詳細設計"
status: active
version: 1.4
updated: 2026-08-14
owner: hide
implements: FLW-FR-003, FLW-FR-004, FLW-FR-005, FLW-FR-006, FLW-FR-007, FLW-FR-008, FLW-FR-009, FLW-FR-010, FLW-NFR-003, FLW-NFR-005, FLW-NFR-006, FLW-CON-002, FLW-CON-004, FLW-CON-005, FLW-CON-006
origin: FLW-REV-002
---

# FLW-DSN-012 Operation Contract詳細設計

## 目的

公開action、policy、result、test、SKILL.mdのnext actionを、同じOperation Contractから導出する。
command実装を先に作らず、各操作の対象・副作用・成功・再実行可能性を先に凍結する。

## 共通contract

各operationは次のfieldを必須とする。

| field | 内容 |
|---|---|
| `operation` | `<domain>.<action>`の安定名 |
| `write_target` | `none`（read）/ `local` / `remote` |
| `reversibility` | `none`（read）/ `reversible` / `destructive` |
| `class` | 上記2軸から導出する互換値。直接決定しない |
| `target` | repo identity、host/owner/repo、ref、path等のcanonical target |
| `preconditions` | plan時とapply直前に照合する事実 |
| `effects` | 許可された副作用の上限。列挙外は実行しない |
| `approval` | `none` / `mutation` / `external-write` / `explicit-human` |
| `postconditions` | `DONE`を外部状態から一意に判定する条件 |
| `retry` | `safe` / `reconcile-first` / `manual-only` |
| `concurrency_key` | 同じtargetへ同時writeさせない直列化キー |
| `partial` | 完了段階と残存段階 |
| `evidence` | resultへ残す秘密値を含まない証跡 |
| `recovery` | writeが参照するFLW-DSN-013の安定Recovery ID。readは空 |

`approval`はCLIが人間本人を認証したことを表さない。実行前に必要な外部裁定の強さを表す。

### operation class の正規導出（SI-FLW-049）

operation class の正は本書の `write_target` と `reversibility` の直交2軸である。互換用の4値
`class` は次の規則だけから導出し、他文書で独自に分類しない。

| `write_target` | `reversibility` | 導出 `class` |
|---|---|---|
| `none` | `none` | `read` |
| `local` | `reversible` | `local-write` |
| `remote` | `reversible` | `remote-write` |
| `local` / `remote` | `destructive` | `destructive` |

`write_target: none` と `reversibility: none` は必ず組にし、write operation に `none` を使わない。
`approval` はこの2軸と独立した第3軸である。

## 公開action catalog

| operation | write_target | reversibility | class | approval | postcondition | retry | recovery |
|---|---|---|---|---|---|---|---|
| `repo.inspect/capabilities` | none | none | read | none | snapshot/capability取得 | safe | — |
| `git.status/diff-summary/diff-detail/log/branches/conflicts` | none | none | read | none | snapshot付きresult | safe | — |
| `git.fetch` | local | reversible | local-write | mutation | FETCH_HEAD/refspec照合 | reconcile-first | `REC-FETCH` |
| `git.stage` | local | reversible | local-write | mutation | index tree一致 | reconcile-first | `REC-STAGE` |
| `git.commit` | local | reversible | local-write | mutation | parent/tree/message digest一致のcommit存在 | reconcile-first | `REC-COMMIT` |
| `git.sync` | local | reversible | local-write | mutation | branchがexpected upstreamへff一致 | reconcile-first | `REC-SYNC` |
| `git.publish-branch` | remote | reversible | remote-write | explicit-human | remote ref=expected HEAD | manual-only | `REC-PUSH` |
| `git.delete-remote-branch` | remote | destructive | destructive | explicit-human | remote ref不存在 | manual-only | `REC-PUSH` |
| `worktree.plan/list/audit` | none | none | read | none | 対象分類取得 | safe | — |
| `worktree.create/resume` | local | reversible | local-write | explicit-human | path/branch/HEAD/common-dir一致 | reconcile-first | `REC-WORKTREE-CREATE` |
| `worktree.finish` | local | destructive | destructive | explicit-human | 対象worktree/local branch不存在 | reconcile-first | `REC-WORKTREE-FINISH` |
| `worktree.discard` | local | destructive | destructive | explicit-human | 列挙したtargetだけ不存在 | manual-only | `REC-WORKTREE-DISCARD` |
| `issue.list/view/search/verify-link/reconcile-link` | none | none | read | none | updatedAt付きresult/repair plan | safe | — |
| `issue.prepare` | none | none | read | none | body digestとplan生成 | safe | — |
| `issue.publish` | remote | reversible | remote-write | external-write | marker/URL一致 | reconcile-first | `REC-ISSUE-PUBLISH` |
| `issue.edit` | remote | reversible | remote-write | external-write | digest一致 | reconcile-first | `REC-ISSUE-EDIT` |
| `issue.comment` | remote | reversible | remote-write | external-write | marker一致 | reconcile-first | `REC-ISSUE-COMMENT` |
| `issue.close` | remote | reversible | remote-write | external-write | state一致 | reconcile-first | `REC-ISSUE-CLOSE` |
| `pr.prepare/checks/merge-plan/post-merge` | none | none | read | none | head/base/check/review証跡 | safe | — |
| `pr.publish` | remote | reversible | remote-write | external-write | PR URL/marker/head一致 | reconcile-first | `REC-PR-PUBLISH` |
| `pr.ready` | remote | reversible | remote-write | external-write | draft=false/head一致 | reconcile-first | `REC-PR-READY` |
| `pr.merge` | remote | destructive | destructive | explicit-human | MERGED/head/merge commit確認 | reconcile-first | `REC-PR-MERGE` |
| `release.plan/changelog/notes` | none | none | read | none | change-set/preview digest | safe | — |
| `release.changelog-apply` | local | reversible | local-write | mutation | file digest一致 | reconcile-first | `REC-CHANGELOG-APPLY` |
| `release.tag-create` | local | reversible | local-write | mutation | local annotated tag=target | reconcile-first | `REC-TAG-CREATE` |
| `release.tag-push` | remote | reversible | remote-write | external-write | remote tag=target | reconcile-first | `REC-TAG-PUSH` |
| `release.draft` | remote | reversible | remote-write | external-write | draft URL/tag/notes digest一致 | reconcile-first | `REC-RELEASE-DRAFT` |
| `release.publish` | remote | destructive | destructive | explicit-human | published URL/tag/target一致 | manual-only | `REC-RELEASE-PUBLISH` |

上表にないoperationは`UNSUPPORTED`。`gh api`やGit subcommandを利用者入力から透過実行しない。

## 正規状態への写像

| 正規WorkUnit state | worktree state | PR state | 許可action |
|---|---|---|---|
| `PLANNED` | `ABSENT` | none | worktree.create |
| `ISOLATED` | `CLEAN` | none | status、作業開始 |
| `ACTIVE` | `DIRTY` | none | diff、stage、commit |
| `VERIFIED` | `CLEAN` | local-verified/prepared | pr.prepare/publish |
| `PR_DRAFT` | `CLEAN` / `DIRTY` | draft/checks-* | pr.checks/ready |
| `REVIEW_READY` | `CLEAN` / `DIRTY` | review-ready | pr.merge-plan |
| `MERGE_READY` | `CLEAN` / `DIRTY` | merge-ready | pr.merge |
| `MERGED` | `CLEAN` / `DIRTY` | merged | pr.post-merge |
| `AUDITED` | `CLEAN` / `DIRTY` | post-merge-audited | worktree.finish（DIRTYは退避receipt必須） |
| `FAILED_RETAINED` | `DIRTY` / `MISMATCH` | 任意 | audit/discard planのみ |
| `CLEANED` | `ABSENT` | merged | 終端 |
| `DISCARDED` | `ABSENT` | 任意 | 終端 |

状態遷移は外部事実から毎回再構成する。単一の証拠で複数状態に該当する場合は、
より危険側の状態を採用し`BLOCKED`にする。

上表の「正規WorkUnit state」12値と「worktree state」の**enum 値としての正は`FLW-DSN-016`§2**
（`work_unit_state` / `worktree_state`）である。本表は両者の対応関係と許可actionを示す。
`FLW-REV-011:SYN-001`は、値の正が複数文書へ分散して確定しない状態をP0としたため、
値そのものは`FLW-DSN-016`の1箇所に置き、設計・schema・実装の三者照合で機械検証する。

### Release state

| Release state | 必要証跡 | 許可action |
|---|---|---|
| `planned` | version/component/target SHA/change set | changelog/notes |
| `changelog-drafted` | preview digest | changelog-apply |
| `changelog-landed` | changelog commitがtargetから到達 | tag-create |
| `tagged-local` | local annotated tag=target | tag-push |
| `tagged` | remote tag=target | draft |
| `release-draft` | draft URL/tag/notes digest一致 | publish |
| `published` | published URL/tag/target一致 | 終端 |

## milestone allocation

| milestone | operations |
|---|---|
| M0 | `repo.inspect`, `git.status`, `git.diff-summary` |
| M1 Git operations | M0対象と`git.delete-remote-branch`を除く`git.*`、`flow-doctor` |
| M2 worktree | 全`worktree.*`、`git.delete-remote-branch` |
| M3 Issue/SDD | `repo.capabilities`、全`issue.*` |
| M4 PR | 全`pr.*` |
| M5 Release | 全`release.*` |

各公開operationは1つのmilestoneだけへ所属する。後続milestoneは前段の公開契約を意味変更しない。

## result data契約

envelopeに加え、全operation dataは次を持つ。

```json
{
  "target": {},
  "preconditions": [],
  "effects": [],
  "postconditions": [],
  "concurrency_key": null,
  "evidence": [],
  "completed_steps": [],
  "remaining_steps": [],
  "cause": null,
  "items": [],
  "page": {"shown": 0, "total": 0, "cursor": null}
}
```

- operation別JSON Schemaが必須field・型・enum・cardinalityを定める。
- 未知fieldは許容するが既存fieldの意味を変えない。
- blocking/error項目を最優先し、次に変更対象、通常項目の順でrenderする。
- mutation判断に全件確認が必要なのに上限超過した場合、applyを`BLOCKED`にする。
- cursorはsnapshotへ拘束し、snapshotが変われば`STALE`。

## operation identity

- `operation_id`: target、snapshot、effectsの一致検査。承認証明ではない。
- `idempotency_id`: 同じ副作用を外部状態から識別する操作別ID。必要なGitHub writeだけmarkerへ埋め込む。
- `approval`: 外部で得た裁定の種別と任意の参照。CLIは本人性を保証しない。

## concurrency

- 全writeは`repo identity + operation family + canonical target`から`concurrency_key`を作る。
- 同一host process群ではGit common-dir配下のowner-only lock fileを対象に、Unixは`fcntl.flock`、
  Windowsは`msvcrt.locking`を使うper-target advisory lockで直列化する。
- process終了でOS lockが解放される方式だけを使い、lock fileの存在だけを所有証明にしない。
- 利用platformで安全なadvisory lockを取得できなければwrite operationを`UNSUPPORTED`へ縮退する。
- Git自身のindex/ref lockを迂回しない。lock競合はbounded wait後に`BLOCKED`。
- 別host/clone間の排他を証明できないGitHub createは、同じWorkUnitを単一coordinatorだけへ割り当てる
  運用前提をplanへ表示する。
- create直後にmarkerを再検索し、複数生成を検出したら自動close/deleteせず`BLOCKED`。
- 同一`idempotency_id`の並行applyを安全に直列化できない実行環境ではcreateを`UNSUPPORTED`へ縮退する。

## 代替案

- command実装ごとに個別schemaを考える: driftを生むため不採用。
- operation IDを承認tokenにする: エージェントが転記できるため不採用。
- 全resultを無条件に全件返す: token目標を満たせないため不採用。

## 影響とロールバック

FLW-DSN-003/005〜010は本catalogへ従属する。M0でschemaとread-only 3操作を固定し、
write actionはcontractとfault fixtureが揃うまでapplyを実装しない。
