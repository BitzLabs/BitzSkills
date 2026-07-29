---
id: FLW-DSC-000
title: "bitz-flow v2 ディスカバリー作業台帳"
status: draft
version: 1.1
updated: 2026-07-29
owner: hide
---

# bitz-flow v2 ディスカバリー作業台帳

## 入力資料

- `docs/調査報告/05.GIT-GHスキル/Gitスキル設計.md`
- `docs/調査報告/05.GIT-GHスキル/GitHub CLI（gh）スキル設計.md`
- 現行 `plugins/bitz-flow/skills/` と同梱スクリプト
- `SI-FLW-001`〜`SI-FLW-005`
- Git / GitHub / GitHub CLI の公式仕様（2026-07-29確認）

## 調査資料から採用する原則

| 原則 | 採否 | v2での扱い |
|---|---|---|
| 生CLI出力を構造化・圧縮する | 採用 | 許可リストschema、件数上限、段階取得 |
| Git / gh CLIを決定論的実行エンジンにする | 採用 | Python dispatcherから固定引数で呼ぶ |
| diffをsummary→detailで取得する | 採用 | cacheではなくsnapshot fingerprint + 再計算 |
| 書込み結果を成否と識別子へ縮小する | 採用 | head SHA、Issue/PR URL、release tag、next state |
| raw出力をキャッシュしhashで復元する | 延期 | 初期版は永続cacheを持たず、path/hunkで再取得 |
| ASTでdiffを意味要約する | 不採用 | 言語依存・意味欠落のため安全判定に使わない |
| token自律監査agent | 対象外 | bitz-flow自身のunit/eval計測に縮小 |

## 現行v1のギャップ

1. `flow-core` / `flow-worktree` / `flow-pr` に入口が分散する。
2. SKILL.md に生 `git` / `gh` コマンドとスクリプトの両方があり、迂回可能。
3. `commit_lint.py`、`branch_preflight.py`、`worktree_ops.py`、`pr_helper.py` で
   終了コード・JSON・診断語彙が統一されていない。
4. `flow-doctor` はスクリプトを持たず、モデルが生出力を解釈する。
5. worktree は並列時だけで、単独作業の物理分離は規定しない。
6. worktree のリポジトリ外配置と、事前承認が必要なガードレールの接続が弱い。
7. SDD接続は `github_issue:` の例示に留まり、一意性・逆リンク・task関係を検証しない。
8. Issue type、sub-issue、dependency、Projects を扱わない。
9. release / CHANGELOG がない。
10. output budget、truncation、token/byte benchmark がない。

## 既存 spec-issue の継承

| Issue | v2への継承 |
|---|---|
| SI-FLW-001 | squash済みbranch終端化、head SHA照合、到達性、冪等cleanupを安全policyへ継承 |
| SI-FLW-002 | fetchとinspectの分離、工程別error taxonomy、鮮度の明示へ一般化 |
| SI-FLW-003 | `git branch audit` の読み取り専用操作として採用 |
| SI-FLW-004 | worktree有無をtarget classifierで吸収し、branch-only cleanupを同じ状態機械で扱う |
| SI-FLW-005 | PRをprepare/publish/ready/checks/merge/post-mergeへ分け、外部状態から再開 |

Issueの status は本再設計だけでは変更しない。要件化時に origin と実施記録を整理する。

## 利用者向けスキル分割候補

| 案 | 実行率 | 自己完結 | 保守性 | 判定 |
|---|---:|---:|---:|---|
| A. `flow-core` 1入口 + `flow-doctor` | 高 | 高 | 高 | **採用候補** |
| B. git-ops / gh-ops / worktree / pr / release | 中 | 低〜中 | 中 | スキル間発動とpath解決が増えるため却下 |
| C. 現行4スキルを改善 | 中 | 高 | 低〜中 | 迂回経路とschema分散が残るため却下 |

## dispatcher 内部モジュール候補

```text
flow-core/
├── SKILL.md
├── references/
│   ├── operation-catalog.md
│   ├── output-contract.md
│   ├── safety-policy.md
│   ├── worktree-workflow.md
│   ├── issue-sdd-linkage.md
│   ├── pr-workflow.md
│   └── release-workflow.md
└── scripts/
    ├── flow.py
    └── flowlib/
        ├── cli.py
        ├── result.py
        ├── process.py
        ├── policy.py
        ├── git_read.py
        ├── git_write.py
        ├── github_read.py
        ├── github_write.py
        ├── worktree.py
        ├── issue.py
        ├── pull_request.py
        └── release.py
```

`flow.py` 以外をエージェントへ直接呼ばせない。内部モジュールは責務・unit test・mock境界のために
分ける。

## worktree 初期提案

- **既定path**: `<repo-parent>/.worktrees/<repo-slug>/<work-id>/`
- **work-id**:
  - SDD taskあり: 小文字化した task ID（例 `flw-tsk-010`）
  - GitHub Issueあり: `gh-<number>`
  - どちらもない: `local-<YYYYMMDD>-<slug>`
- **branch**: `<type>/<work-id>-<slug>`
- **作成前**: default branch、remote、base SHA、path collision、branch collision をplanで提示。
- **承認**: repo外書込みとなるためapply前にユーザー承認。
- **再開**: path / branch / registered worktree / HEAD が一致すれば同一作業としてresume。
- **完了**: merged evidence → worktree remove → local branch cleanup → remote再照会。
- **失敗**: 自動削除せずretain。明示discardは変更要約と対象再確認後に別操作として実行。

## SDD / GitHub Issue 初期提案

| 概念 | SSOT | GitHubでの表現 |
|---|---|---|
| 変更提案と人間裁定 | `.spec/spec-issues` | accepted後にparent Issueとして公開可能 |
| 契約 | `.spec/requirements` | Issue本文から参照するがIssue化しない |
| 実行単位 | `.spec/tasks` | 並列・共有が必要ならsub-issue |
| 依存 | task `depends_on` | Issue dependencyへ外向き同期 |
| 作業状態 | task status | Project Statusへ外向き同期可能 |
| 実装差分 | Git commit / PR | `Implements:` と task / Issue link |

GitHubから `.spec` の人間専用statusを変更しない。ラベルにIDを埋め込まず、IDは本文の
固定markerと `.spec` frontmatter URLで双方向に保持する。

## ラベル / Issue type 初期提案

- Issue typeが利用可能なら `Feature` / `Bug` / `Task` を使う。
- 利用不能時だけ `type:feature` / `type:bug` / `type:task` labelへfallbackする。
- workflow labels: `flow:ready`、`flow:blocked`、`sdd:linked`。
- release labels: `release:breaking`、`release:skip`。
- priority / size / iteration はGitHub Projectsのfieldを使い、labelを増やさない。
- spec IDごとのlabelは作らない。

## Open Questions

| 論点 | 状態 | 裁定 |
|---|---|---|
| 「200UE」の意味 | resolved | ユーザー裁定により「ISSUE」の誤記として確定（2026-07-29） |
| 実装言語 | resolved | Python 3.10+に固定。Go言語は使用・移行候補ともにNG（2026-07-29） |
| CHANGELOG単位 | resolved | repository modeをMust、component modeをShould |
| GitHub Projects | resolved | 初期Should。M3 Must後に昇格 |
| repo外worktree承認 | resolved | 設定は権限を代替せず、createごとに外部確認 |
| 旧skill pointer | resolved | v2 majorで削除。migration doctor/noteで移行 |

## Discovery Gate

- 裁定: Go（進行可・条件付き。プログラミング言語のGoを指さない）
- 裁定者: hide
- 裁定日: 2026-07-29
- 条件: MCP、Rust化、プラットフォーム固有hook、透過proxyを実装対象から恒久的に除外する
- 根拠: `assumptions.md`
