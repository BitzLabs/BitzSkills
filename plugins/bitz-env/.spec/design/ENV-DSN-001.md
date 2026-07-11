---
id: ENV-DSN-001
version: 1.0
status: approved
domain: deploy
origin: 製作プラン（2026-07-11 人間承認済み）からの移送
---

# ENV-DSN-001 bitz-env アーキテクチャ

製作プラン（人間承認済み）の設計部分を `.spec/` へ移送したもの。実装 v0.1.0 の根拠。

## 可否判定の要点（設計の前提）

- permissions（settings.json の deny/allow）はプラグインで直接配布**できない**
  → PreToolUse フックで実行時ブロック + env-init が permissions を生成、の2層で代替
- サブエージェントのモデルエイリアスは Claude Code 固有 → 雛形配布 + セットアップ時選択
- Claude Code のプラグイン `rules/` 自動マージは仕様上未確認 → ルール文書は生成方式が確実

## 2層構造

| 層 | 実体 | 効き始め | 特性 |
|---|---|---|---|
| 即効層 | 同梱 PreToolUse フック（hooks/hooks.json + hooks.json + scripts/env_guard.py） | プラグイン有効化直後 | プロジェクトに書き込まない。プラグイン無効化で消える |
| 生成層 | env-init が生成する permissions / AGENTS.md / CLAUDE.md 断片 / advisor・worker | env-init 実行後 | プラグイン無効時も効く恒久層。更新に自動追従しない（env-doctor が差分検出） |

同一ガードレールの意図的な二重化。3層（permissions ⇔ フック ⇔ ナラティブ）の
同期ズレは env-doctor の診断対象（ENV-FR-007）。

## ガード共通ロジック（env_guard.py）

- 1スクリプトで両プラットフォーム対応。stdin の JSON 形状で自動判別（ENV-FR-002）
- Claude Code: `hooks/hooks.json`（ラッパー形式・snake_case・`${CLAUDE_PLUGIN_ROOT}`）
- Antigravity: ルート `hooks.json`（camelCase・matcher `run_command`・相対パス。
  `${CLAUDE_PLUGIN_ROOT}` 相当が無いため cwd = hooks.json の場所を前提）
- deny は普遍的最小集合に限定（ENV-CON-001）。ガードの故障は素通し（fail-open）—
  恒久層（permissions）が二重に守るため、フック側は可用性を優先する

## モデル非依存の協調運用

- 中心 = ユーザー選択モデル。役割は相対定義（advisor / worker）。ENV-FR-005
- 3パターン: 委譲型（中心→worker）/ 相談型（中心→advisor、最終判断は中心）/
  合議型（複数へ並列諮問、裁定は多数決でなく中心。発動条件は高影響判断に限定）
- 劣化動作の連鎖: 合議不成立→相談型へ格下げ→advisor 不在→単独判断（明記付き）

## 協調アダプタ機構

- ハブ＆アダプタ。契約 = collab-contract.md v1（公開契約・後方互換拡張 ENV-CON-002）
- 連携は「契約（スキル名 delegate/review/status + metadata.collab 能力宣言）+
  プロジェクト内レジストリ `.claude/bitz-env.local.md`」の疎結合
  （プラグイン同士は相互のファイルを参照できないため）
- bitz-env はアダプタゼロでも完全に機能する（純粋追加式）

## 要検証項目（実環境での実測待ち）

1. プラグイン有効化時のフック同意ダイアログの有無
2. Claude Code でのプラグイン内 `rules/*.md` の読み込み挙動
3. 展開先の既存フックとの共存（二重発火）
4. セッション内からの有効プラグイン一覧の取得手段（不能なら手動登録フォールバック）
