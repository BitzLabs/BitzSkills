---
id: FLW-DSN-014
title: "GitHub capability・M0検証設計"
status: active
version: 1.0
updated: 2026-07-29
owner: hide
implements: FLW-FR-003, FLW-FR-008, FLW-FR-012, FLW-NFR-001, FLW-NFR-002, FLW-NFR-004
origin: FLW-REV-002
---

# FLW-DSN-014 GitHub capability・M0検証設計

## 目的

GitHub host、repository feature、権限、gh CLI版による差を、実行時の推測やraw fallbackではなく
capability contractで吸収する。また、write機能へ進む前に単一dispatcherの価値をM0で検証する。

## capability state

| state | 意味 |
|---|---|
| `AVAILABLE` | 必要なread/write経路とscopeを確認済み |
| `DEGRADED` | fallback契約で目的を満たせる |
| `UNSUPPORTED` | host/repositoryが機能を持たない |
| `UNAVAILABLE` | auth/network/rate limit等で現在判定不能 |

判定時刻、host、owner/repo、gh version、認証主体の非秘密識別子、必要scope、検査stageを返す。
planとapplyでhost/owner/repo/認証主体が変われば`STALE`。

## GitHub capability matrix

| capability | 初期scope | primary | fallback |
|---|---|---|---|
| Issue CRUD/search | Must | high-level `gh issue` | なし |
| Issue type | Must | high-level option | `type:*` label |
| sub-issue | Must | high-level optionがあれば使用 | allowlist固定endpoint adapter |
| issue dependency | Must | high-level optionがあれば使用 | allowlist固定endpoint adapter |
| Projects fields | Should | high-level `gh project` | 無効化してDEGRADED |
| PR CRUD/checks/review | Must | high-level `gh pr` JSON | 不足fieldは固定endpoint adapter |
| branch protection | Should | high-level/API read | 読取不能ならmergeをBLOCKED |
| merge queue | Should | capability read | 初期版はqueue投入UNSUPPORTED |
| Release CRUD | Must | high-level `gh release` | なし |

固定endpoint adapterは、source codeに列挙したmethod・path template・response fieldだけを
`gh api`経由で実行する。利用者入力のURL、method、GraphQL document、任意fieldを受け取らない。
これはGitHub adapterの内部実装であり、透過proxyや任意API passthroughではない。

## capability検出

1. local remoteからcanonical host/owner/repoを導出する。
2. gh versionとauth hostを照合する。
3. read-onlyなhelp/schema/feature probeを行う。
4. action別scopeとrepository featureを判定する。
5. mutationを伴うprobeは行わない。
6. rate limitまたは権限不足をfeature不存在と誤判定しない。

## M0 Contract Kernel

M0は独立PR 1件で次だけを実装する。

- `repo inspect`
- `git status`
- `git diff-summary`
- result envelopeとoperation別JSON Schema
- compact renderer、snapshot、truncation/cursor
- process runner、Git read adapter
- `flow-core`のMandatory entry protocol
- 3platform evalとgolden fixture

write operation、GitHub network operation、worktree作成はM0に含めない。

## M0 eval protocol

| 項目 | 固定条件 |
|---|---|
| platforms | Claude Code / Codex CLI / Antigravity 2.0 |
| model record | provider、model ID、version/dateをrun manifestへ記録 |
| tasks | repo inspect、dirty status、rename/binaryを含むdiff-summary |
| trials | platform×taskごとに10回 |
| prompt | version管理した同一prompt |
| oracle | 最初のGit操作がflow.py、schema一致、期待snapshot/field一致 |
| baseline | skillなしとv1 skillの両方 |
| retry | agentによる自己再試行は失敗。harness再実行は別trial |

### M0出口条件

- platformごとのDispatcher Invocation Rate 95%以上、かつskillなしbaseline比20ポイント以上改善。
- platformごとのSFCR 90%以上。全体平均で相殺しない。
- Cross-model Decision Parity 100%。
- 必須field保持100%、golden schema一致100%。
- raw fallback、状態変更、秘密値出力、黙ったtruncationが各0件。
- statusのmedian byte削減70%以上、diff-summaryのmedian byte削減80%以上。
- 操作別p90とabsolute byte上限をfixture manifestへ固定し、以後の回帰判定に使う。

1条件でも未達ならM1へ進まず、description、入口名、schema、rendererを修正してM0を再実行する。
5回の作業sessionまたは1PRで出口に到達しない場合はscope/pivotを人間へ再提示する。

## M1〜M5出口

| milestone | 出口 |
|---|---|
| M1 Git operations | 残るGit read/writeとdoctor、operation contract全行、fault fixture、重複commit 0 |
| M2 worktree | repo identity衝突0、repo外承認、finish/discard fault全通過 |
| M3 Issue/SDD | capability matrix、marker重複0、link reconcile全通過 |
| M4 PR | push/PR/merge各partialから収束、CI/head誤判定0 |
| M5 Release | changelog atomicity、tag/draft収束後にpublishを段階有効化 |

component release、Projects、merge queueはMust出口を満たした後に個別昇格する。

## 代替案

- 全GitHub機能を高水準gh commandだけに限定: Mustを満たせない版差があるため不採用。
- 任意`gh api` passthrough:安全境界が消えるため不採用。
- M1全体を作ってからskill eval:主目的の失敗判明が遅すぎるため不採用。

## 影響

FLW-DSN-004/007/008/010とscope/metricsを本matrix・M0へ揃える。
