---
id: FLW-DSN-000
title: "bitz-flow v2 設計作業台帳"
status: draft
version: 1.1
updated: 2026-07-29
owner: hide
---

# bitz-flow v2 設計作業台帳

## 設計原則

1. 利用者向け入口は `flow-core` の `flow.py` に一本化する。
2. SKILL.md には通常経路の生 `git` / `gh` コマンドを載せない。
3. 読取と状態変更、planとapply、完了cleanupと失敗discardを分離する。
4. 安全判定には決定論的な事実だけを使い、LLM要約を使わない。
5. 省略は必ず可視化し、追加取得の条件を返す。
6. `.spec` のstatusをbitz-flowから変更しない。

## API 導出表

| API | 層 | 依存 | 由来 |
|---|---|---|---|
| `repo inspect` | System | Git | 全操作の前提 |
| `git status/diff/log/branch` | System | Git | 低tokenの状態把握 |
| `git fetch/stage/commit/sync` | System | Git | 安全なローカル変更 |
| `worktree *` | Process | Git system APIs | worktree-first |
| `issue *` | Process | GitHub system APIs | 実行・協調台帳 |
| `pr *` | Process | Git + GitHub | Draft→CI→merge |
| `release *` | Process | Git + GitHub | CHANGELOG→tag→release |
| compact renderer | Experience | Result envelope | AI向け既定出力 |
| JSON renderer | Experience | Result envelope | テスト・連携 |

## 技術適合性

| 候補 | 適合性 | 判断 | 根拠 |
|---|---|---|---|
| Python 3.10+標準ライブラリ | High | Adopt | 3platform共通、スキル内自己完結、既存資産 |
| Go言語 | None | Reject | ユーザー制約。実装・部分置換・移行比較の対象外 |
| Git machine-readable output | High | Adopt | porcelain / NUL区切りで決定論的 |
| `gh --json` | High | Adopt | allowlist field取得、認証をghへ委譲 |
| SQLite等の内部DB | Low | Reject | 外部状態から再開でき、内部SSOTを増やす必要がない |
| LLMによるdiff要約 | None | Reject | 安全判定の再現性を失う |

## Open Questions

| 論点 | 裁定 | 根拠 |
|---|---|---|
| CHANGELOG component設定 | deferred | repository modeをM5 Must、component modeをShouldとする（FLW-DSN-009/014） |
| GitHub Projects | deferred | Should。M3 MustのIssue/SDD接続後に昇格（FLW-DSN-014） |
| repo外worktree rootの継続承認 | rejected | 設定は配置既定値だけ。実行時権限を代替しない（FLW-DSN-006/013） |
| 固定GitHub endpoint adapter | adopted with constraint | Must不足機能だけをsource allowlistで実行（FLW-DSN-014） |
| release publish初期提供 | staged | M5前半draft、fault fixture通過後の後半で有効化（FLW-DSN-009/014） |
| 実装言語 | adopted | Python 3.10+のみ。成立しない場合はscope縮小・再設計・No-Go |
