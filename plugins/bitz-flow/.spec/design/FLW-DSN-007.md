---
id: FLW-DSN-007
title: "GitHub Issue・BitzSDD接続詳細設計"
status: active
version: 1.0
updated: 2026-07-29
owner: hide
implements: FLW-FR-008, FLW-NFR-003, FLW-NFR-005, FLW-NFR-006, FLW-CON-003, FLW-CON-004
origin: FLW-DSC-003
---

# FLW-DSN-007 GitHub Issue・BitzSDD接続詳細設計

## 責務分離

| 情報 | SSOT | bitz-flowの責務 |
|---|---|---|
| 変更提案・accept/reject | `.spec/spec-issues` | 参照markerをIssueへ載せる |
| EARS契約・approve | `.spec/requirements` | IDを参照するだけ |
| 実行タスク・depends_on | `.spec/tasks` | 必要時にsub-issue/dependencyへ外向き投影 |
| 共有進捗・会話 | GitHub Issue / Project | CRUDと短い状態取得 |
| 実装差分 | Git / PR | Issue/task/specへのtrace |

bitz-flowはbitz-sddへ依存せず、`.spec` fileやstatusを変更しない。リンクの記録はsdd側が担う。

## SDD連携フロー

1. accepted spec-issueまたはapproved taskをsdd側が選ぶ。
2. `flow issue prepare --spec-issue SI-* --task * --requirement *`でbody draftを生成。
3. 人間がplanを確認し`issue publish`。
4. resultはIssue URL、number、trace markerを返す。
5. sdd側がspec-issue/taskへURLを記録する。
6. `issue verify-link`がGitHub markerとsdd側から渡された期待ID/URLを照合する。
7. 片側欠落や重複は`issue reconcile-link`がread-only repair planとして返す。

open spec-issueをpublishする場合は「提案・未裁定」であることを明示し、実装Issueとして
`flow:ready`にしない。

## trace marker

Issue本文に可視の固定節を置く。

```text
## Bitz Trace
- Spec-Issue: SI-FLW-002
- Requirements: FLW-FR-003, FLW-NFR-001
- Task: FLW-TSK-010
- Work-Unit: flw-tsk-010
```

- IDが無い行は省略する。
- requirementをIssueそのものとして複製しない。
- 1 taskは高々1 open Issue、1 spec-issueは高々1 active parent Issue。
- link identityは`source-kind + source-id + issue-url`。requirementは複数Issueから参照できる。
- URLをlabelへ埋め込まない。
- create/comment系writeは本文末尾にFLW-DSN-013のidempotency markerを1つ置く。

## Issue階層

- accepted spec-issue / featureをparent Issue。
- 並列実行・共有が必要なtaskをsub-issue。
- task `depends_on`をIssue dependencyへ投影。
- 小さなlocal taskはIssue化を必須にしない。
- GitHubからtask statusを自動更新せず、sdd status変更後の外向き同期だけを許可する。
- sub-issue/dependencyの高水準gh操作が無い場合はFLW-DSN-014のallowlist固定endpoint adapterを使う。

## type / label / Project

Issue type利用可能:

- Feature: 機能・改善のparent
- Bug: 不具合
- Task: 実行sub-issue

利用不能時だけ`type:feature|bug|task`へfallback。

固定labels:

- `flow:ready`
- `flow:blocked`
- `sdd:linked`
- `release:breaking`
- `release:skip`

priority、size、iteration、statusはProject fieldを優先し、labelを増やさない。Project操作は
必要scopeとfield IDの事前検出ができた場合だけ実行する。

## Issue CLI

- read: list/view/search/verify-link/reconcile-link
- draft: prepare
- write: publish/edit/comment/close
- publish/edit/closeはplan/apply、numberとupdatedAt相当の鮮度を再照会する。
- bodyは必ずfile経由で渡し、shell引数へ長文を埋め込まない。
- publish/commentの応答喪失はmarker検索後にだけ再実行する。

## reconcile-link

| state | 判定 | plan |
|---|---|---|
| `linked` | markerと期待URLが相互一致 | 変更なし |
| `github-only` | Issue markerあり、sdd URLなし | sdd側へ記録すべきURLを返す |
| `sdd-only` | sdd URLあり、markerなし | Issue edit planを返す |
| `duplicate` | 同じsourceのactive Issueが複数 | BLOCKED、人間選択 |
| `stale` | URLまたはIDが不一致 | BLOCKED、両側証跡を返す |

bitz-flowはrepair planを返すだけで`.spec`を書き換えない。Issue側editも別applyとする。

## failure

`auth-missing`, `scope-missing`, `feature-unavailable`, `duplicate-link`,
`parent-not-found`, `dependency-cycle`, `stale-issue`, `network-unavailable`へ正規化する。

## 代替案

- 全requirementをIssue化: 契約と実行の二重SSOTになるため不採用。
- spec IDごとのlabel: label爆発とrename問題のため不採用。
- GitHub statusから`.spec`を逆更新: 人間裁定を迂回するため禁止。

## 影響

bitz-sdd側にはURL記録とverify-link呼出の接続変更が将来必要だが、本設計はbitz-flow単体の
opaque ID契約として実装できる。
