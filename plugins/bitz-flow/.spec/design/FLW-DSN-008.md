---
id: FLW-DSN-008
title: "PRライフサイクル詳細設計"
status: active
version: 1.0
updated: 2026-07-29
owner: hide
implements: FLW-FR-009, FLW-NFR-003, FLW-NFR-005, FLW-NFR-006, FLW-CON-002, FLW-CON-004
origin: SI-FLW-005
---

# FLW-DSN-008 PRライフサイクル詳細設計

## 状態

```text
local-verified
  → prepared
  → draft-published
  → checks-pending / checks-failed / checks-passed
  → review-ready
  → merge-ready
  → merged
  → post-merge-audited
```

各actionはGitHubを再照会して現在状態を導出する。内部progress fileは持たない。
正規WorkUnit stateとの写像はFLW-DSN-012、部分失敗はFLW-DSN-013に従う。

## prepare

前提:

- worktree/branch/HEADが一致
- default branchとの差分あり
- branchがterminalでない
- 同head branchのmerged PRなし
- 同branchのopen PRは0件または再開対象1件
- commit lintと指定verification evidenceがgreen

生成物:

- Conventional Commits準拠title
- 目的、変更点、検証結果、trace、closing keywordを持つbody file
- expected head SHA、base、labels、reviewerを含むpublish plan
- 本文末尾のidempotency marker

## publish

1. expected HEADを再照会。
2. forceなしでbranchをpush。
3. 同branch open PRを再照会。
4. 無ければDraft PR作成、あれば一致するPRをresume。
5. PR number、URL、head SHA、base、draft stateを返す。

push成功後にPR作成が失敗した場合は`PARTIAL`。再実行は既存remote branchを再利用し、
head branchとmarkerを照合してPRを重複作成しない。複数一致は`BLOCKED`。

## checks / ready

- `checks`はrequired優先で`pass/fail/pending/skipping/cancel`へ正規化する。
- pendingは完了としない。watch timeoutは`UNAVAILABLE`または`BLOCKED`で状態を保持する。
- `ready`はhead SHA、checks、review request、baseを再確認してDraftを解除する。
- branch protectionがreviewを要求する場合、review decision未充足を`BLOCKED`。

## merge plan

必須証跡:

- state OPEN、draft false
- headRefOid = expected head
- baseRefName = expected default
- mergeable / mergeStateStatusが許容
- required checks pass
- required review decision充足
- unresolved blocking Issueなし
- stacked PRでない（head branchをbaseとするopen PRなし）
- titleがsquash subject契約に適合

planはPR number、head SHA、base SHA、subject、closing Issues、operation IDを返す。

## merge

- planのoperation IDを要求する。
- 外部の明示的人間確認を要求する。
- apply直前に全証跡を再照会する。
- squashとexpected head SHAを指定する。
- admin bypassを提供しない。
- remote branch削除をmergeへ連結しない。
- 成功後にMERGED、merge commit、mergedAtを再照会し、確認できなければ`PARTIAL`。
- merge応答喪失時は同じoperationを再送せず、PR state/head/merge commitのreconcileを先に行う。

## post-merge

1. merge commitのdefault到達を確認。
2. closing Issue状態とtraceを確認。
3. worktree auditへmerged evidenceを渡す。
4. cleanupはFLW-DSN-006へ委譲。

## 未マージ依存

stacked PRは作成しない。依存PRを先にlandし、最新defaultから別WorkUnitを作る。
Issue dependency / task depends_onが未解決ならworktree投入とPR readyを`BLOCKED`にする。

## 診断

`duplicate-pr`, `terminal-branch`, `empty-diff`, `wrong-base`, `head-mismatch`,
`checks-pending`, `checks-failed`, `review-required`, `merge-conflict`,
`dependency-blocked`, `stacked-pr`, `merge-queue`, `network-unavailable`。

merge queueが必須の場合は直接mergeせず、queue投入と完了確認を別状態として扱う。

## 影響

現行`branch_preflight.py`と`pr_helper.py`をdispatcher moduleへ統合し、SI-FLW-002/005の
診断と再開性を一般化する。
