---
id: FLW-DSN-002
title: "bitz-flow v2 ドメインモデル"
status: active
version: 1.0
updated: 2026-07-29
owner: hide
implements: FLW-FR-003, FLW-FR-006, FLW-FR-008, FLW-FR-009, FLW-FR-010, FLW-CON-003
origin: FLW-DSC-001
---

# FLW-DSN-002 bitz-flow v2 ドメインモデル

## 背景

現行v1はbranch、worktree、PRの個別手順から実装を始めたため、操作結果・証跡・状態遷移の
共通語彙がない。v2は「コマンド」ではなく、エージェントが安全に開発作業を進めるための
概念を先に固定する。

## 主要概念

| 概念 | 意味 | 識別子 |
|---|---|---|
| RepositoryContext | repo root、Git common dir、HEAD、current/default branch、remote、dirty状態 | canonical repo path |
| WorkUnit | 1つの関心事。worktree、branch、Issue、PRを束ねる | SDD task ID / Issue番号 / local ID |
| Snapshot | 読取時点のHEAD・index・worktree・remote headのfingerprint | SHA-256 digest |
| OperationPlan | apply前の対象、前提、予定副作用、必要な外部裁定種別 | operation ID |
| OperationResult | 判定、短い根拠、構造化data、warning、next action | schema + operation |
| Evidence | test、CI、review、merged PR、tag等の検証可能な事実 | 種別固有ID/SHA/URL |
| WorktreeTarget | path、branch、HEAD、Git登録状態を組にした対象 | work ID |
| IssueLink | GitHub Issueとspec-issue/task/requirementの型付き参照 | source kind + source ID + Issue URL |
| PullRequestState | DraftからmergedまでのGitHub上の状態 | PR番号 + head SHA |
| ReleasePlan | version、component、change set、tag、notes、公開条件 | tag + target SHA |

## 集約と不変条件

### Operation集約

- `OperationPlan` とapply時の再計算結果が一致しなければ状態変更しない。
- planは副作用ゼロ、applyはplanが列挙した副作用を越えない。
- `OperationResult` はraw stdout / stderrやcredentialを保持しない。
- operation IDは鮮度・対象・予定副作用の一致検査であり、人間承認の証明に使わない。
- 重複し得るwriteはoperation別idempotency identityとpostconditionを持つ。

### WorkUnit集約

- v2で新規作成する1 WorkUnit = 1 worktree = 1 branch = 0..1 GitHub Issue = 0..1 open PR。
- v1から移行するbranch-only対象はworktree 0を許容し、cleanup専用のlegacy形として分類する。
- 同じbranchを複数WorkUnitへ割り当てない。
- squash merge済みbranchはterminalであり再利用しない。
- failureとcompletionは別の終端状態とし、同じcleanup操作を共有しない。

### SDD Link集約

- `.spec`が仕様・裁定のSSOT、GitHubが協調・実行状態のSSOT。
- requirementは契約でありGitHub Issueへ複製しない。
- bitz-flowは`.spec`のstatusを変更しない。
- IssueLinkは`source_kind`、`source_id`、`issue_url`の組で一意にする。
- 1 taskは高々1 open Issue、1 spec-issueは高々1 active parent Issue、1 requirementは複数Issueから
  参照可能とする。requirement参照はIssueとの所有関係を意味しない。
- marker側とsdd側URL記録の片側欠落はreconcile planで検出し、bitz-flow自身は`.spec`を変更しない。

### Release集約

- release対象は明示したtarget SHAへ固定する。
- CHANGELOGとrelease notesは同じchange setから生成する。
- version bump、build、署名はプロジェクト側の証跡でありbitz-flowが推測実行しない。

## 状態機械

```text
WorkUnit:
planned → isolated → active → verified → pr-draft → review-ready
  → merge-ready → merged → audited → cleaned
                └→ failed-retained → discarded（外部の明示的人間確認）

Release:
planned → changelog-drafted → changelog-landed → tagged
  → release-draft → published
```

`failed-retained` から `cleaned` へ直接遷移しない。未コミット変更を含む失敗作業は、
明示的なdiscard裁定があるまで保持する。

domain固有状態、遷移証跡、許可action、終了コードの正規写像はFLW-DSN-012を正とする。
副作用の成否を外部状態から一意に確定できない場合は状態を進めず`INDETERMINATE`とする。

## 代替案

- Gitコマンド単位だけのモデル: workflow横断の証跡と再開点を表せないため不採用。
- 内部DBをSSOTにする: Git / GitHubと三重管理になるため不採用。
- PRをWorkUnitより大きくする: 並列worktreeとrollback境界が崩れるため既定にしない。

## 影響範囲

`flow-core` の公開語彙、全result schema、worktree / Issue / PR / releaseの状態機械へ波及する。
Operation ContractはFLW-DSN-012、復旧はFLW-DSN-013、規範切替はFLW-DSN-011に従う。
実装前のdraftなので、ロールバックはv2設計一式を破棄しv1-currentを維持する。
