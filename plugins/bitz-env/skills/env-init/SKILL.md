---
name: env-init
description: bitz-env の開発環境（ガードレール permissions・AGENTS.md/CLAUDE.md 雛形・advisor/worker サブエージェント）を対象プロジェクトへ対話的に展開する。「開発環境を展開して」「環境をセットアップして」「ガードレールを入れて」「協調環境を初期化して」「env-init」と言われたとき、または bitz-env 導入直後の初期設定時に使用する。展開済み環境の診断は env-doctor、協調アダプタの登録は env-register が担当する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-11"
---

# env-init

## 目的

bitz-env プラグインが定義する開発環境 — ガードレール（機械強制 + ナラティブ）と
モデル非依存の協調運用（中心・advisor・worker） — を、対象プロジェクトへ
**ユーザー確認付きで**書き出す。プラグイン同梱フックは導入時点で既に有効なので、
本スキルはそれを補完する「生成層」を担当する。

## 原則

- **書き出しは必ずユーザー確認付き**。既存ファイルがある場合は上書きせず、
  diff を提示してマージ案を出す
- **生成物は自己完結**。プラグインの更新に自動追従しない（差分検出は env-doctor が行う）
- **再実行可能**。CLAUDE.md / AGENTS.md への挿入はマーカーコメント
  `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->` で囲み、再実行時はその区間だけ再生成する

## ワークフロー

### 1. 環境の確認

対象プロジェクトのルートで以下を確認する:

- プラットフォーム: Claude Code / Antigravity / 両方（ユーザーに質問）
- 既存ファイルの有無: `.claude/settings.json`、`AGENTS.md`、`CLAUDE.md`、`.claude/agents/`
- Git リポジトリか（そうでなければ先に `git init` を提案）

### 2. 中心モデルと役割の割り当て

ユーザーに「普段このプロジェクトで使うモデル（中心）」を聞き、割り当てを提案する:

| 中心モデル | advisor（相談先） | worker（委譲先） | 主なパターン |
| --- | --- | --- | --- |
| 最上位（Opus 等） | なし（不要） | Sonnet / Haiku | 委譲型のみ |
| 中位（Sonnet 等） | Opus | Haiku | 委譲型 + 相談型 |
| 軽量（Haiku 等） | Opus / Sonnet | なし | 相談型が主体 |

提案はあくまで既定値。ユーザーの予算・プラン制約に応じて変更してよい。
Antigravity のみの環境ではモデルエイリアスが解釈されないため `inherit` を用いる。

### 3. 生成（すべて確認付き）

| 生成物 | テンプレート | 内容 |
| --- | --- | --- |
| `.claude/settings.json` | `references/permissions.md` | deny/ask の permissions（既存があればマージ案を提示） |
| `AGENTS.md` | `references/templates/AGENTS-template.md` | ガードレール節 + 検証義務（`{{project}}` を置換） |
| `CLAUDE.md`（断片挿入） | `references/templates/CLAUDE-fragment.md` | 役割ベースの委譲マトリクス + 今回の割り当て表 |
| `.claude/agents/advisor.md` | `references/templates/advisor.md` | 相談役（`{{model}}` を手順2の割り当てで置換）。中心が最上位なら生成しない |
| `.claude/agents/worker.md` | `references/templates/worker.md` | 作業役（同上）。中心が軽量なら生成しない |

### 4. 検証と報告

- 生成した JSON が正しくパースできるか `python3 -m json.tool <ファイル>` で確認する
- 生成・スキップ・マージした項目の一覧をユーザーに報告する
- 次のステップを案内する: 協調アダプタ（外部エージェント連携）があれば env-register、
  運用ルールの詳細は env-orchestration、定期診断は env-doctor

## してはいけないこと

- ユーザー確認なしの既存ファイル上書き
- マーカー区間の外にある既存記述の変更
- プロジェクト固有でない場所（ホームディレクトリ等）への書き込み
