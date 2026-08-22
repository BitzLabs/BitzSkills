---
id: FLW-DSC-003
title: "bitz-flow v2 スコープ"
status: draft
version: 2.4
updated: 2026-08-22
owner: hide
---

# bitz-flow v2 スコープ

## 制約

- Agent Skills のフォルダ単体コピーで動作する自己完結性を守る。
- Python 3.10+、Git、必要時のみ GitHub CLI を外部前提とし、Python の追加依存は持たない。
- 実装言語はPython 3.10+に固定する。Goによる実装、再実装、部分置換、移行比較を行わない。
  Pythonで必須安全契約を満たせない場合はscope縮小、設計変更、またはNo-Goを裁定する。
- Claude Code / Codex CLI / Antigravity 2.0 に共通する最小能力である「スキル読込 + CLI実行」
  を正規経路にする。
- GitHub 認証情報は `gh` に委ね、bitz-flow は token・credential を読み取らない。
- 禁止操作（`git reset --hard`、force push、`git clean -f`、`rm -rf`、`sudo`）を
  実装・提案しない。
- リポジトリ外に worktree を作る場合は、実行前にパスを提示してユーザー承認を得る。
- M2のwrite safetyは、同一OSユーザーが管理するローカルrepository、Git common-dir、ローカル
  filesystemを信頼境界とする。同一OSユーザーによる悪意ある改ざん、network filesystem、remote writeは
  M2の保証対象にしない。

## MoSCoW

### Must — v2 初期版

1. **単一 dispatcher**
   - `flow-core/scripts/flow.py` を通常操作の唯一の入口にする。
   - `--format compact|json`、共通終了コード、timeout、許可リスト診断を全操作で共有する。
2. **Git 読取**
   - repo context、status、diff summary/detail、log、branch/worktree audit、conflict 検出。
   - Git の安定した machine-readable 出力を parse し、上限と絞込み導線を持つ。
3. **Git 状態変更**
   - fetch、worktree create/resume、明示 path の stage、commit、ff-only sync。
   - branch publishと、merged evidence付きの独立remote branch削除。
   - 状態変更は plan と apply を分離し、stale snapshot を拒否する。
4. **worktree-first**
   - 書込み作業は単独でも worktree が既定。
   - 作成、再開、一覧、完了 cleanup、失敗保全、明示 discard を状態機械化する。
5. **GitHub Issue**
   - list/view/search/prepare/publish/edit/comment/close/verify-link/reconcile-link。
   - issue type、sub-issue、dependency を capability 検出つきで扱う。
   - 高水準`gh`で不足するMust機能は、method/path/fieldをsource codeへ固定した内部adapterで扱う。
   - BitzSDD の spec-issue / task との双方向リンクを検証する。
6. **PR**
   - prepare、push、Draft publish、checks、ready、merge plan/apply、post-merge audit。
   - squash、expected head SHA、CI/review/base 条件、冪等再開を契約化する。
7. **release**
   - 前回 tag 以降の merged PR 収集、分類、CHANGELOG draft、release notes draft、
     tag 検証、GitHub Release draft / publish。
   - プロジェクト固有 version bump・build・sign は外部工程として証跡だけ受け取る。
8. **独立 doctor**
   - Git、GitHub CLI、Python、remote/default branch、認証・必要 scope を読み取り専用診断する。
9. **検証**
   - unit / fault injection / golden output / token-byte benchmark / cross-platform path test。
   - skill-tester で script invocation rate を計測する。
   - M0 read-only thin sliceで3platformの価値を実証してからwrite operationへ進む。

### Should — 初期版に余力があれば

- GitHub Projects への item add と Status / Priority / Size 更新。
- Issue type が使えない repository 向けの fallback label 初期化。
- branch protection / merge queue の capability 読取と merge 待機。
- monorepo component 単位の CHANGELOG / release notes（repository modeの後に昇格）。
- `flow.py explain <code>` による短い復旧案。

### Could — 後続

- output cache / cursor cache。初期版は再計算 + snapshot fingerprint を使う。
- GitLab / Forgejo adapter。

### Won't — v2 初期版では行わない

- 任意 shell / 任意 `gh api` passthrough。
- rebase、履歴書換え、force push、stash を通常フローに含める。
- GitHub token の保存・注入。
- LLM による diff の意味要約を安全判定の入力にする。
- 自動 version bump、任意 build command の実行、署名鍵操作。
- GitHub Project を `.spec` status の SSOT にする。
- 失敗 worktree を自動削除する。
- M2での署名capability、reviewer key registry、root of trust、key rotation/revocation。
- M2 operation journalのarchive、prune、restore、自動削除。
- M2運用CLIのRBAC、通知adapter、運用RTO/SLO。

## リリース分割

### M0: Contract Kernel

`repo inspect`、`git status`、`git diff-summary`、result schema、renderer、process runner、
3platform evalだけを独立PRで実装する。platform別Invocation 95%、SFCR 90%、skillなし比20pt改善、
parity 100%、危険操作0を満たさなければM1へ進まない。

### M1: Git operations

残るGit read、fetch、stage、commit、sync、publish-branch、doctorのOperation Contractとfault fixture。

### M2: worktree-first

worktree の配置・命名・作成・再開・audit・cleanup・保全・discard、独立remote branch削除。

### M3: Issue / SDD

Issue CRUD、sub-issue / dependency、`.spec` 双方向リンク、fallback label、reconcile-link。

### M4: PR

Draft publish、CI/review gate、expected head squash merge、post-merge cleanup。

### M5: Release

repository modeのCHANGELOG、release notes、tag / release gate。draftまでを前半、
fault fixture通過後にpublishを後半で有効化する。component modeはShouldとして別途昇格する。

各milestoneは1件以上の「1 PR = 1関心事」から成る独立した出荷・rollback境界にし、
M0をlandしてから後続を開始する。各PRは単独revert可能に保ち、milestone全体のrollbackは
直前milestoneのplugin version/revisionへpinして当該milestoneのPR集合を無効化する。
詳細な出口条件、最大PR/session予算、予算超過時の縮退出荷境界はFLW-DSN-014を正とする。
M2未完了ではworktree-first境界が閉じないためM1 Git writeを公開せずM0へ縮退する。
M3以降は直前milestoneまでをprerelease出荷できるが、未完了operationは`UNSUPPORTED`とする。
各縮退出荷境界は、その境界自身までの独立canaryがgreenの場合だけ公開する。
縮退版をcurrentへ昇格する場合はscope変更としてDesign GateとPromotion Gateを再裁定する。
