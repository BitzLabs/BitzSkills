---
id: FLW-DSN-005
title: "Git操作カタログ詳細設計"
status: active
version: 1.0
updated: 2026-07-29
owner: hide
implements: FLW-FR-004, FLW-FR-005, FLW-NFR-003, FLW-CON-002
origin: FLW-DSC-003
---

# FLW-DSN-005 Git操作カタログ詳細設計

## 分類原則

- `read`: Git object/ref/index/worktreeを変更しない。
- `local-write`: local ref/index/worktreeを変更する。
- `remote-write`: remote refを変更する。
- すべてのwriteはplan/apply。stage/commitもsnapshot一致を要求する。
- class、approval、postcondition、retryの正はFLW-DSN-012とする。

## Read operations

| action | 主なGit入力 | 既定出力 |
|---|---|---|
| `repo inspect` | `rev-parse`, status porcelain v2 | root、HEAD、branch、upstream、dirty、remote |
| `git status` | `status --porcelain=v2 --branch -z` | XY、path、rename、ahead/behind、件数 |
| `git diff-summary` | `diff --name-status -z`, `--numstat -z` | path、kind、added/deleted、binary |
| `git diff-detail` | `diff --no-ext-diff --unified=1` | 指定path/hunkの変更行、snapshot |
| `git log` | `log --format` + NUL separator | short SHA、subject、author date、parents |
| `git branches` | `for-each-ref --format` | local/remote、SHA、upstream、ahead/behind |
| `git conflicts` | `diff --name-only --diff-filter=U -z` | conflict path一覧 |
| `worktree list` | `worktree list --porcelain` | path、HEAD、branch、locked/prunable |

pathはNUL区切りを優先し、改行・空白・非ASCIIを含むfilenameを損なわない。
Git configによるpager、color、external diffを無効化する。

## Diffの段階取得

1. `diff-summary`で全体のpathと変更量を取得する。
2. エージェントが必要pathを選び`diff-detail --path`を呼ぶ。
3. detailは最大bytes / 最大hunksを受け、超過を明示する。
4. summaryとdetailのcanonical bytesからsnapshot fingerprintを計算する。
5. 呼出時の`--snapshot`と再計算値が違えば`STALE`。

初期版はraw diff cacheを持たない。working treeが変わった場合は古い詳細を復元せず、再取得する。

## Write operations

| action | plan内容 | apply |
|---|---|---|
| `git fetch` | remote、refspec、prune有無 | 明示remoteだけfetch |
| `git stage` | explicit pathspec、現在snapshot | `git add -- <paths>` |
| `git commit` | staged snapshot、lint済message、expected branch | stdin優先でcommit |
| `git sync` | default/upstream、ahead/behind、dirty | fetch後`merge --ff-only` |
| `git publish-branch` | remote、branch、expected HEAD、upstream | forceなしpush |
| `git delete-remote-branch` | remote、branch、expected remote SHA、merged evidence | exact refだけ削除 |

- `git add .`相当は提供せずpathを明示する。
- commit messageはConventional Commitsと任意のWorkUnit / Implements footerを事前検査する。
- commit messageはstdinを優先する。fileが必要な下位CLIではFLW-DSN-013のowner-only temp規約を使う。
- remote writeは必ずtarget remote / ref / expected HEADをplanへ出す。
- remote branch削除は独立actionとし、finish/mergeへ自動連結しない。

## 明示的な非対応

- reset、clean、force push。
- rebaseと既存公開branchの履歴書換え。
- stashを使う暗黙退避。
- 任意Git subcommand passthrough。
- git config、remote add/remove等の環境構築。

## 診断cause

`not-repository`, `invalid-ref`, `invalid-path`, `dirty`, `detached-head`, `no-upstream`,
`non-fast-forward`, `conflict`, `timeout`, `command-unavailable`, `permission-denied`,
`snapshot-mismatch`, `remote-unavailable`, `result-indeterminate`。

## 検証

- path quoting、rename/copy、binary、submodule、initial repo、detached HEAD。
- staged/unstaged/untracked、conflict、ahead/behind。
- snapshot変更、timeout、Git errorのsanitization。
- plan時とapply時のcommand sequence、副作用ゼロfixture。
- 各writeの応答喪失後postconditionとFLW-DSN-013 recovery matrix。

## 代替案と影響

GitPython等は追加依存とGit CLIとの差異が増えるため不採用。既存`commit_lint.py`は機能を
moduleへ移し、旧CLIはv2で削除する。
