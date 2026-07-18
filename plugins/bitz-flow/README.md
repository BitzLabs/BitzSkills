# bitz-flow — Git / GitHub 開発フロー

状況に応じた Git / GitHub 開発フローの選択・コミット規約・worktree 並列運用・
Issue 駆動 PR フローを規定する**独立プラグイン**です。

> **単体で使えます**: SDD（仕様駆動開発 / `bitz-sdd` プラグイン）を採用していない
> プロジェクトでも導入できます。bitz-sdd を併用しているプロジェクトでは、
> 各スキル末尾の「bitz-sdd 併用時」節が接続点（Implements フッター・`.spec/tasks` 連携・
> 権限マトリクス）を規定し、SDD 側の規約が優先されます。

## 収録スキル

| スキル | 役割 |
|---|---|
| `flow-core` | フロー選択の判断表（単独=feature ブランチ / 並列=worktree / チーム=Issue 駆動 PR）、ブランチ規約、Conventional Commits のコミット規定、失敗時の復元方針 |
| `flow-worktree` | 複数エージェント並列の分離手段。1エージェント = 1 worktree = 1ブランチの原則、作成・マージバック、squash merge 証跡付き cleanup、失敗時破棄の定型手順 |
| `flow-pr` | GitHub Issue 駆動フロー。Issue 起票 → branch preflight → Draft PR → CI ゲート → squash merge、マージ済み head の終端化、未マージ依存の原則 |

### 発動の例

- 「このプロジェクトの Git フローを決めたい」「コミット規約は？」 → `flow-core`
- 「worktree で並列開発したい」「失敗したからやり直したい」 → `flow-worktree`
- 「Issue 駆動で進めたい」「PR の運用ルールは？」 → `flow-pr`

## インストール

```
# Claude Code
/plugin marketplace add BitzLabs/BitzSkills
/plugin install bitz-flow@bitzskills

# Antigravity 2.0
agy plugin install <このリポジトリ>/plugins/bitz-flow

# OpenAI Codex CLI
codex plugin marketplace add BitzLabs/BitzSkills
codex plugin add bitz-flow@bitzskills
```

## 経緯

`bitz-sdd` の `sdd-git` スキルから汎用部分を切り出して新設されました（SI-CORE-008）。
その後 SI-CORE-010 で sdd-git は薄い委譲ポインタに縮退され、Git フローの実行手順の正は
本プラグイン（flow-core / flow-worktree / flow-pr）に一本化されています
（bitz-sdd は `metadata.dependencies` で `bitz-flow>=0.2` を宣言）。
