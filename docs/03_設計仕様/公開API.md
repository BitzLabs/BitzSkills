---
id: DOC-design-public-api
title: 公開APIと互換性
status: active
version: 0.1.0
changeImpact: low
project_type: library
updated: "2026-07-27"
owner: hide
superseded_by: null
---

# 公開APIと互換性

このリポジトリの「利用者」は、マーケットプレイスからプラグインを導入する Claude Code /
Antigravity 2.0 / Codex CLI のユーザーである。公開契約は言語 API ではなく、
プラグイン／スキルの名前空間と frontmatter・CLI インタフェースである。

## 公開面 (Public Surface)

| 契約単位 | 安定度 | 備考 |
|---|---|---|
| プラグイン名・`source` パス（marketplace.json） | `stable` | リネーム・移動は破壊的変更として `!` コミット必須 |
| スキル名（`plugins/*/skills/<name>`） | `stable` | プレフィックス規約（CORE-CON-005）に従う |
| SKILL.md frontmatter 契約（name/description/metadata） | `stable` | 仕様の正: `plugins/skill-creator/skills/skill-creator/references/spec.md` |
| `.spec` 成果物 frontmatter 契約（id/status/version 等） | `stable` | 正: bitz-sdd の sdd-core |
| `scripts/spec {inspect,scaffold,status,update}` CLI | `stable` | 引数・終了コードの意味を変える場合は破壊的 |
| `scripts/release_check.py` / `scripts/bump_version.py` の CLI 呼び出し形 | `stable` | AGENTS.md の定型手順が依存 |
| 各スキル内部の `scripts/` 実装詳細 | `internal` | 契約外。予告なく変更してよい |
| `docs/調査報告/` の内容 | `internal` | 参照専用の検証済み仕様メモ。契約ではない |

安定度の意味:
- **stable** … SemVer の完全対象。破壊はプラグイン version の major bump でのみ。
- **experimental** … 現時点でこのリポジトリに該当区分の契約は無い。
- **internal** … 公開ディレクトリに存在しても契約外（スキル内部実装、調査報告等）。

## 互換性ポリシー (SemVer)

対象は各プラグインの `version`（3マニフェスト共通値。CORE-CON-001）。

- **MAJOR**: スキル名・frontmatter 必須キー・CLI 引数など stable 契約を壊す変更。
- **MINOR**: 後方互換な追加（新スキル・新 frontmatter 任意キー・新 CLI サブコマンド）。
- **PATCH**: 契約に影響しない修正（文言修正・内部実装のみの変更）。

> 原則: **追加は additive に**。既存のスキル名・frontmatter キーの意味は変えず、新規追加で拡張する。
> version bump は変更を届ける同一 PR に含める（コミット位置は問わない。CORE-CON-010）。

## 非推奨ポリシー (Deprecation)

1. 代替スキル・代替キーを用意してから非推奨化する。
2. `.spec` 要件は `superseded_by` で後継要件を明示し、旧要件は `status` を移行させる
   （例: CORE-FR-004/005 → 後継要件への移行実績あり）。
3. スキル・プラグインの削除は次の major でのみ。破壊的変更は Conventional Commits の
   `!` を付けたコミット（`refactor!:` 等）で明示する。

## リポジトリ固有の具体（3プラットフォーム共通契約）

### プラグイン配布（3マニフェスト）
- Claude Code / Antigravity 2.0 / Codex CLI 向けにそれぞれ独立したマニフェストを持つが、
  `name` と `version` は常に同値（CORE-CON-001）。
- 追加・削除は `.claude-plugin/marketplace.json` の `plugins[]` との双方向整合を要する
  （CORE-CON-003）。

### SKILL.md frontmatter
- 必須: `name`（親フォルダ名一致）・`description`。`metadata.version` は semver で、
  内容変更のたびに bump し `updated` を更新する（CORE-CON-002）。
- 非推奨化: 後継スキルへの言及を `description` またはドキュメントに残し、削除は
  プラグイン major bump に合わせる。

### `.spec` 成果物 frontmatter
- 要件は `id` / `status` / `version` / `superseded_by` を持ち、廃止時は `status` を更新し
  `superseded_by` に後継 id を記載する（新規要件は削除せず履歴を保持）。

### `scripts/spec` CLI（inspect/scaffold/status/update）
- Claude / Codex 双方の固定インストール版をバージョン非依存に解決する
  （`.spec/design/DSN-004.md`、CORE-FR-011）。引数形式・終了コードの意味変更は破壊的。

### `<plugin名>:update` の移行機構
- 配置先に残す状態（frontmatter スキーマ・レジストリ形式）の変更は宣言的 Markdown +
  guard 必須の累積マイグレーションで移行する（CORE-CON-009、`.spec/design/DSN-002-update-migration.md`）。
  中間バージョンの欠落時は安全側停止。

## サポートマトリクス（3プラットフォーム対応状況）

| 項目 | Claude Code | Antigravity 2.0 | Codex CLI |
|---|---|---|---|
| マーケットプレイス導入 | `/plugin marketplace add` → `/plugin install` | `agy plugin install <path>` | `codex plugin marketplace add` → `codex plugin add` |
| マニフェスト | `.claude-plugin/plugin.json` | `plugin.json` | `.codex-plugin/plugin.json` |
| `allowed-tools` frontmatter | 対応 | 未対応（無視される） | TBD（未検証。参照: `docs/調査報告/03.Codex/`） |
| bitz-env のガードレール機械強制（フック） | `.claude/settings.json` permissions + フック | プラグイン同梱フック | 未対応。スキルと AGENTS.md 規律のみ利用する段階（`00_はじめに/対象外.md`。正式劣化モードは SI-ENV-023 で追跡） |
| `scripts/spec` の固定版解決 | `installed_plugins.json` 経由 | 対象外（本リポジトリでは非所有） | `codex plugin list --json` 経由（DSN-004） |

Codex CLI 向けの完全対応（特に `bitz-env` の機械フック・`env-init`）は現時点で未達であり、
3プラットフォームへの配布は全コンポーネントの機能同等性を意味しない（`00_はじめに/対象外.md`）。

## 移行ガイドの置き場

- 破壊的変更（major）ごとに、該当プラグインの変更履歴（コミットログ・`Revision History`）に
  移行手順を記載する。専用の移行ガイドファイルを設ける規模の破壊的変更は、現時点では実績が無い
  （TBD: 発生時に `06_リファレンス/` 相当の置き場を検討）。

---
### Revision History
| version | date | change | impact |
|---|---|---|---|
| 0.1.0 | 2026-07-27 | 初版（テンプレートから実内容へ書き換え） | — |
