---
id: FLW-DSN-012
title: "Operation Contract詳細設計"
status: active
version: 1.1
updated: 2026-07-29
owner: hide
implements: FLW-FR-003, FLW-FR-004, FLW-FR-005, FLW-FR-006, FLW-FR-007, FLW-FR-008, FLW-FR-009, FLW-FR-010, FLW-NFR-003, FLW-CON-002
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
| `class` | `read` / `local-write` / `remote-write` / `destructive` |
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

## 公開action catalog

| operation | class | approval | postcondition | retry | recovery |
|---|---|---|---|---|---|
| `repo.inspect/capabilities` | read | none | snapshot/capability取得 | safe | — |
| `git.status/diff-summary/diff-detail/log/branches/conflicts` | read | none | snapshot付きresult | safe | — |
| `git.fetch` | local-write | mutation | FETCH_HEAD/refspec照合 | reconcile-first | `REC-FETCH` |
| `git.stage` | local-write | mutation | index tree一致 | reconcile-first | `REC-STAGE` |
| `git.commit` | local-write | mutation | parent/tree/message digest一致のcommit存在 | reconcile-first | `REC-COMMIT` |
| `git.sync` | local-write | mutation | branchがexpected upstreamへff一致 | reconcile-first | `REC-SYNC` |
| `git.publish-branch` | remote-write | external-write | remote ref=expected HEAD | reconcile-first | `REC-PUSH` |
| `git.delete-remote-branch` | destructive | explicit-human | remote ref不存在 | reconcile-first | `REC-REMOTE-DELETE` |
| `worktree.plan/list/audit` | read | none | 対象分類取得 | safe | — |
| `worktree.create/resume` | local-write | explicit-human | path/branch/HEAD/common-dir一致 | reconcile-first | `REC-WORKTREE-CREATE` |
| `worktree.finish` | destructive | explicit-human | 対象worktree/local branch不存在 | reconcile-first | `REC-WORKTREE-FINISH` |
| `worktree.discard` | destructive | explicit-human | 列挙したtargetだけ不存在 | manual-only | `REC-WORKTREE-DISCARD` |
| `issue.list/view/search/verify-link/reconcile-link` | read | none | updatedAt付きresult/repair plan | safe | — |
| `issue.prepare` | read | none | body digestとplan生成 | safe | — |
| `issue.publish` | remote-write | external-write | marker/URL一致 | reconcile-first | `REC-ISSUE-PUBLISH` |
| `issue.edit` | remote-write | external-write | digest一致 | reconcile-first | `REC-ISSUE-EDIT` |
| `issue.comment` | remote-write | external-write | marker一致 | reconcile-first | `REC-ISSUE-COMMENT` |
| `issue.close` | remote-write | external-write | state一致 | reconcile-first | `REC-ISSUE-CLOSE` |
| `pr.prepare/checks/merge-plan/post-merge` | read | none | head/base/check/review証跡 | safe | — |
| `pr.publish` | remote-write | external-write | PR URL/marker/head一致 | reconcile-first | `REC-PR-PUBLISH` |
| `pr.ready` | remote-write | external-write | draft=false/head一致 | reconcile-first | `REC-PR-READY` |
| `pr.merge` | destructive | explicit-human | MERGED/head/merge commit確認 | reconcile-first | `REC-PR-MERGE` |
| `release.plan/changelog/notes` | read | none | change-set/preview digest | safe | — |
| `release.changelog-apply` | local-write | mutation | file digest一致 | reconcile-first | `REC-CHANGELOG-APPLY` |
| `release.tag-create` | local-write | mutation | local annotated tag=target | reconcile-first | `REC-TAG-CREATE` |
| `release.tag-push` | remote-write | external-write | remote tag=target | reconcile-first | `REC-TAG-PUSH` |
| `release.draft` | remote-write | external-write | draft URL/tag/notes digest一致 | reconcile-first | `REC-RELEASE-DRAFT` |
| `release.publish` | destructive | explicit-human | published URL/tag/target一致 | manual-only | `REC-RELEASE-PUBLISH` |

上表にないoperationは`UNSUPPORTED`。`gh api`やGit subcommandを利用者入力から透過実行しない。

## 正規状態への写像

| 正規WorkUnit state | worktree state | PR state | 許可action |
|---|---|---|---|
| `planned` | absent/planned | none | worktree.create |
| `isolated` | active-clean | none | status、作業開始 |
| `active` | active-dirty | none | diff、stage、commit |
| `verified` | active-clean | local-verified | pr.prepare |
| `verified` | active-clean | prepared | pr.publish |
| `pr-draft` | pr-open | draft-published | pr.checks/ready |
| `pr-draft` | pr-open | checks-pending/checks-failed/checks-passed | pr.checks/ready |
| `review-ready` | pr-open | review-ready | pr.merge-plan |
| `merge-ready` | pr-open | merge-ready | pr.merge |
| `merged` | merged-exact | merged | pr.post-merge |
| `audited` | merged-exact | post-merge-audited | worktree.finish |
| `cleaned` | absent | merged | 終端 |
| `failed-retained` | active-dirty/orphan | 任意 | audit/discard planのみ |
| `discarded` | absent | 任意 | 終端 |

状態遷移は外部事実から毎回再構成する。単一の証拠で複数状態に該当する場合は、
より危険側の状態を採用し`BLOCKED`にする。

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
