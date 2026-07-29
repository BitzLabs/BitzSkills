---
id: FLW-DSC-004
title: "bitz-flow v2 ペルソナとJTBD"
status: draft
version: 2.0
updated: 2026-07-29
owner: hide
---

# bitz-flow v2 ペルソナと JTBD

ペルソナの感情や利用頻度は未調査のため `[proto / 未検証]` とする。ここでは操作契約を
導くために、利用者と実行主体を分けて記述する。

## Persona A — 開発を委ねる人間

- **状況**: 複数のAIエージェント／モデルを切り替えてリポジトリを開発する。
- **Job**: モデルごとに Git / GitHub 手順を教え直さず、安全で追跡可能な成果を得たい。
- **Pain**: コマンドの即興、長い出力、確認漏れ、worktree の残骸、PR / Issue / SPEC の二重管理。
- **成功**: 実行前 plan と実行後 evidence が短い同一形式で示され、必要な裁定だけを行える。

## Persona B — AIエージェント

- **状況**: 限られたコンテキストで、ローカル Git と GitHub の状態を判断する。
- **Job**: 次の安全な一手に必要な情報を少ないトークンで取得し、定型操作を再発明せず実行したい。
- **Pain**: 生出力の揺れ、例外分類不足、スクリプトの所在分散、長い SKILL.md、途中失敗後の再開判断。
- **成功**: どの作業も `flow.py` から始まり、結果に判定コード、根拠、次の許可操作が含まれる。

## Persona C — BitzSDD 利用者

- **状況**: `.spec/spec-issues`、requirements、tasks を仕様の正として運用しつつ、
  GitHub で実行状況を共有する。
- **Job**: 人間専用の裁定権を維持し、GitHub Issue / PR から SPEC へ双方向に辿りたい。
- **Pain**: status の二重管理、spec-issue と GitHub Issue の1対1誤解、要件と作業Issueの混同。
- **成功**: `.spec` が契約、GitHub が協調台帳という境界が機械検証される。

## Persona D — 小規模チームのメンテナ

- **状況**: Issue、PR、release、CHANGELOG を一貫した分類で維持する。
- **Job**: merge 条件と release 内容を短時間でレビューし、中断した自動化を安全に再開したい。
- **Pain**: ラベル増殖、PR title と squash subject の不一致、CI pending の誤merge、release notes の漏れ。
- **成功**: 種別・依存・release category が同じ語彙で連携し、外部状態を再照会して続行できる。

## JTBD

| ID | When | I want to | So I can |
|---|---|---|---|
| J1 | 作業を開始するとき | 最新 default SHA から規約どおりの worktree を作る | 単独作業でも並列化と失敗隔離に備えられる |
| J2 | 変更状況を確認するとき | status / diff を段階的に圧縮取得する | 生出力でコンテキストを埋めず安全に判断できる |
| J3 | 仕様変更をGitHubへ公開するとき | accepted spec-issue と実行 Issue を双方向リンクする | 裁定と実行を混同せず追跡できる |
| J4 | 複数タスクを進めるとき | task を sub-issue、depends_on を dependency として表す | worktree 投入可能性を人とGitHubで共有できる |
| J5 | PRを出すとき | Draft、CI、review、ready、merge を段階実行する | 中断や再試行でPRを重複作成しない |
| J6 | mergeするとき | head SHA と必須checksを再照会してsquashする | stale head や未完了CIを誤ってmergeしない |
| J7 | merge後 | worktree / local / remote branch を証跡つきで片付ける | 作業残骸を減らし、ブランチ再利用事故を防げる |
| J8 | releaseするとき | merged PRからCHANGELOGとrelease notesを作る | 変更履歴をリポジトリとGitHubの双方に残せる |
| J9 | 操作が失敗したとき | 診断分類と外部状態から再開点を得る | 生ログを読み直さず副作用を重複させない |

## Journey

```text
repo inspect / repo capabilities / flow-doctor（利用意図に応じて選択）
  → intake
  → Issue または SDD task の作業ID確定
  → worktree plan
  → ユーザー承認（リポジトリ外書込み）
  → worktree create / resume
  → implement
  → status / diff / verification evidence
  → stage / commit
  → PR prepare / Draft publish
  → checks / review / ready
  → merge plan / head再照会 / squash
  → post-merge audit / cleanup
  → release plan / CHANGELOG PR / release publish
```
