---
id: FLW-DSN-006
title: "worktree-firstライフサイクル詳細設計"
status: draft
version: 1.0
updated: 2026-07-29
owner: hide
implements: 
origin: SI-FLW-001
---

# FLW-DSN-006 worktree-firstライフサイクル詳細設計

## 基本判断

コード・仕様・テストへ書き込む作業は、単独エージェントでもworktreeを既定とする。
main checkoutはcoordinationとread-only inspectionに使い、通常実装を置かない。

## 配置と命名

```text
<repo-parent>/.worktrees/<repo-slug>-<repo-id8>/<work-id>/
```

- repo内走査への混入を避けるためrepo外を既定とする。
- `repo-id8`はcanonical Git common-dirを基本に、利用可能ならcanonical remote identityも含めた
  SHA-256の先頭8文字とする。同名repoを別pathへcloneしてもidentity衝突を検査する。
- repo外writeになるため、`worktree plan`がcanonical pathを提示し、apply前に人間承認を要求する。
- `.bitz-flow.json`の`worktree_root`で承認済みrootを指定できる設計候補を残すが、
  設定だけで現在の実行権限を上書きしない。

Work ID:

1. SDD task: lowercase task ID（例 `flw-tsk-010`）
2. GitHub Issue: `gh-<number>`
3. local: `local-<YYYYMMDD>-<slug>`

branchは`<type>/<work-id>-<slug>`。typeは`feat/fix/docs/refactor/test/chore`。

## create / resume

```text
absent
  → planned
  → approved
  → registered-active
```

planで次を照合する:

- repo/default branch/remote/base SHA
- canonical common-dir、repo identity、remote host/owner/repo
- pathがworktree root直下
- branch/path/work IDのcollision
- 同branchを使う既存worktree
- baseが最新remote defaultか

path、branch、registered worktree、HEADがすべて一致する場合、createは重複作成せず
`resume`を返す。一部だけ一致する場合は`BLOCKED`。

## audit分類

| state | 条件 | 許可 |
|---|---|---|
| `active-clean` | 登録一致・clean | 作業継続 |
| `active-dirty` | 登録一致・変更あり | status/diff/commit |
| `pr-open` | head一致のopen PR | PRフローへ |
| `merged-exact` | merged PR headとbranch SHA一致 | finish plan |
| `remote-advanced` | remoteだけheadから進行 | cleanup拒否・保全 |
| `worktree-mismatch` | path/branch/HEAD不一致 | 停止 |
| `orphan` | directory/ref/registryの一部だけ存在 | 停止・人間確認 |
| `failed-retained` | 失敗裁定、変更を保持 | discard planのみ |

SI-FLW-003のbranch auditとSI-FLW-004のbranch-only cleanupは、targetの存在要素を分類する
同じaudit engineへ統合する。

## finish

PRあり:

1. PR state=MERGED、headRefName、headRefOid、mergeCommitを取得。
2. branch/worktree/remoteの存在対象がheadRefOidと一致することを確認。
3. mergeCommitがremote defaultから到達可能であることを確認。
4. main checkoutがcleanであることを確認しff-only同期。
5. worktree remove。
6. local branchをexact SHA条件つきで削除。
7. remote refを再照会し、削除候補として報告。

remote branch削除はfinishに自動連結しない。削除する場合は独立したremote-write planと
人間確認を要求し、`git delete-remote-branch`へ委譲する。

PRなし:

- normal mergeでbranchがdefaultのancestorならfinish可能。
- squash相当で証跡が不足する場合は差分の見かけだけで削除せず`BLOCKED`。

## failure / discard

- 失敗検出時の既定は`failed-retained`。自動削除しない。
- discard planはdirty file件数、untracked件数、branch SHA、pathを提示する。
- discard planは削除対象path一覧、symlink、submodule、ignored file件数をmanifest化する。
- applyはoperation ID再入力、外部の明示的人間確認、現在状態の一致を要求する。
- 禁止操作を使わず、Gitのworktree removeとbranch削除を列挙targetへ限定して実行する。
- 途中失敗は`PARTIAL`と残存要素を返し、再実行で前進再開する。
- manifestを完全取得できない場合は`BLOCKED`とし、applyしない。

## 検証

collision、path escape、symlink、dirty、別worktree占有、merged/unmerged、head進行、
途中失敗、再実行、branch-only、remote-only、同名repo・clone identity衝突をfault injectionで固定する。

## 影響

現行`worktree_ops.py`のadd/list/cleanup/discardを新状態機械へ置換する。旧CLI互換は持たない。
