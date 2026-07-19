---
name: flow-doctor
description: bitz-flow の各フロー（feature ブランチ / worktree 並列 / Issue 駆動 PR）が前提とする外部ツール環境（git・gh CLI・リモート origin）を読み取り専用で診断する。「flow-doctor」「bitz-flow の診断」「環境診断」「Git 環境を診断して」「gh の認証状態を確認して」と言われたとき、または開発フローの選定・worktree 運用・PR フロー開始前に前提環境を確認したいときに使用する。フロー選択とコミット規約は flow-core、worktree 手順は flow-worktree、Issue 駆動 PR 手順は flow-pr が担当する。
metadata:
  version: "1.0.0"
  author: br7.hide
  created: "2026-07-19"
  updated: "2026-07-19"
---

# flow-doctor — bitz-flow 前提環境の診断

bitz-flow の各フローが動作する前提の外部ツール環境（git・gh CLI・リモート構成）を
**読み取り専用**で診断します。**対象プロジェクト・配置先への書き込みは一切行いません**
（診断と修正案の提示のみ。修正の実施はユーザー判断・ユーザー操作に委ねます）。

## 診断項目

### 1. git の存在とバージョン

- `git --version` を実行し、git コマンドが利用可能か確認する
- worktree 運用（flow-worktree）には git 2.5 以上が必要なため、バージョンが
  2.5 未満、または git 自体が見つからない場合は **FAIL** とし、
  OS のパッケージマネージャ等での導入・更新手順を修正案として示す

### 2. gh CLI の存在と認証状態

- `gh --version` を実行し、gh CLI が利用可能か確認する
  - 見つからない場合、Issue 駆動 PR フロー（flow-pr）を使う運用では **FAIL**、
    使わない運用（feature ブランチ運用のみ等）では **WARN** に留め、
    `https://cli.github.com/` からの導入手順を修正案として示す
- gh CLI が存在する場合は `gh auth status` を実行し、認証済みか確認する
  - 未認証の場合、flow-pr を使う運用では **FAIL**、使わない運用では **WARN** に留め、
    `gh auth login` による認証手順を修正案として示す
- flow-pr を使うかどうかが不明な場合は、ユーザーに用途（feature ブランチ運用のみか、
  Issue 駆動 PR も使うか）を確認したうえで深刻度を判定する

### 3. リモート origin とデフォルトブランチ（Git リポジトリ内のみ）

- 実行環境が Git リポジトリ内かどうかをまず確認する（リポジトリ外なら本項目はスキップし、
  その旨を報告する）
- リポジトリ内であれば `git remote get-url origin` 等でリモート `origin` の有無を確認する
  - 存在しない場合は **WARN**（ローカル専用運用の可能性があるため FAIL にはしない）とし、
    リモート追加手順（`git remote add origin <URL>`）を修正案として示す
- origin が存在する場合、デフォルトブランチが特定できるか確認する
  （例: `git remote show origin` の `HEAD branch`、または `gh repo view --json defaultBranchRef`）
  - 特定できない場合は **WARN** とし、リモート側のデフォルトブランチ設定確認、または
    ローカルでの `git remote set-head origin -a` 実行を修正案として示す

## 出力形式

env-doctor に準じたチェックリスト形式で報告する:

```
# flow-doctor 診断結果

## 前提ツール環境
- [PASS] git: 2.43.0（worktree 運用の要件 2.5 以上を満たす）
- [PASS] gh CLI: 2.50.0 / 認証済み（gh auth status で確認）
- [PASS] リモート origin: 設定あり（https://github.com/...）/ デフォルトブランチ: main

## 総合: OK — 前提環境に問題はありません
```

問題がある場合は該当行を `[FAIL]` または `[WARN]` とし、判定理由と修正案を続けて記す。
全項目が OK の場合は各項目の根拠（バージョン・確認コマンドの結果）を簡潔に添えて
OK 判定を報告する。

## してはいけないこと

- 対象プロジェクト・配置先への書き込み（設定変更・認証操作・リモート追加などの実施）
- ユーザー承認なしの修正実施（診断と修正案の提示に留める。実施はユーザー自身が行う）
