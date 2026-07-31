---
id: FLW-DSN-014
title: "GitHub capability・M0検証設計"
status: active
version: 1.4
updated: 2026-07-31
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

byte削減の測定条件は2026-07-31の裁定（`SI-FLW-007`）で固定した。statusのbaselineは
固定commandではなく**no-skill条件で実際に消費された出力**のbyte数とし、platformごとにmedianを取る。
diff-summaryのbaselineは生unified diff（`git diff <base>`）とする。byte比較は`truncated: false`の
trialだけで行い、省略した出力を全量baselineと比較しない。corpusは規模の異なる3 fixtureとし、
medianはその横断で取る。詳細は`.spec/discovery/metrics.md`の測定条件節と
`.spec/reports/decision-2026-07-31-byte-baseline-measurement.md`。

1条件でも未達ならM1へ進まず、description、入口名、schema、rendererを修正してM0を再実行する。
5回の作業sessionまたは1PRで出口に到達しない場合はscope/pivotを人間へ再提示する。

## M1〜M5出口・timebox・縮退出荷境界

作業sessionは「1エージェントが1つの明示目的に対し、review可能なcommitまたは検証証跡を
生成する連続作業単位」とする。各milestoneはPR予算またはsession予算のどちらかを先に
使い切った時点で停止し、継続、scope縮小、またはNo-Goを人間へ再提示する。

下表は見積実績がない段階の**初期budget**である。各milestone開始時に、直前までの
実績PR数、実績session数、レビュー修正回数、出口未達理由をrun manifestへ記録し、
人間が次budgetの維持または変更を確認する。進行中milestoneの上限を暗黙に延長せず、
変更はdecision reference付きで記録する。

| milestone | 最大予算 | 出口 | 予算超過時の安全な縮退出荷境界 |
|---|---:|---|---|
| M1 Git operations | 3 PR / 12 session | 残るGit read/writeとdoctor、M1所属operationのcontract全行、fault fixture、重複commit 0 | M0 read-only prereleaseだけを維持。Git writeとdoctor v2は公開しない |
| M2 worktree | 2 PR / 8 session | repo identity衝突0、repo外承認、finish/discard fault全通過 | M0 read-only prereleaseへ縮退。worktree-first未完了のためM1 Git writeも公開しない |
| M3 Issue/SDD | 3 PR / 12 session | capability matrix、marker重複0、link reconcile全通過、独立10 Issue/SDD flow canary green | M2までをprerelease出荷し、全`issue.*`を`UNSUPPORTED`にする |
| M4 PR | 3 PR / 12 session | push/PR/merge各partialから収束、CI/head誤判定0、独立10 PR flow canary green | M3までをprerelease出荷し、全`pr.*`を`UNSUPPORTED`にする |
| M5 Release | 2 PR / 8 session | changelog atomicity、tag/draft収束後にpublishを段階有効化 | M4までを出荷。release draftだけがgreenならprerelease限定で公開し、publishは`UNSUPPORTED`にする |

PR予算はmilestone内の実装・fixture・文書・version bumpを含む。レビュー修正は元PRへ含め、
機械的な再実行だけではsessionを加算しない。新しい要件、operation、platform固有分岐を
追加する場合は予算内であってもscope変更として人間へ提示する。

### 縮退時の規則

1. 直前milestoneの公開schemaと挙動を変更しない。
2. 未完了operationは部分公開せず`UNSUPPORTED`とし、生コマンドfallbackを提示しない。
3. M2未完了ではworktree-first安全境界が閉じないため、M1 Git writeを公開しない。
4. M5前半のdraft機能はprerelease限定とし、publishをv2完成条件から黙って除外しない。
5. 縮退版をv2-currentへ昇格する場合は、scope/要件/operation catalogを改訂して
   Design GateとPromotion Gateを再裁定する。
6. 各縮退出荷境界は、その境界自身までの独立canaryがgreenの場合だけ公開する。

component release、Projects、merge queueはMust出口を満たした後に個別昇格する。

## 代替案

- 全GitHub機能を高水準gh commandだけに限定: Mustを満たせない版差があるため不採用。
- 任意`gh api` passthrough:安全境界が消えるため不採用。
- M1全体を作ってからskill eval:主目的の失敗判明が遅すぎるため不採用。

## 影響

FLW-DSN-004/007/008/010とscope/metricsを本matrix・M0へ揃える。
