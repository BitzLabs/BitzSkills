---
id: PLG-DSC-003
title: "plugin-creator スコープ（制約 → MoSCoW → In/Out 境界）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# スコープ — plugin-creator

> 遡及的ディスカバリー。現行リリース（v1.2.1、7スキル + create-plugin コマンド + agent-creator/plugin-validator エージェント）の実体をスコープとして言語化しつつ、SI-CORE-006（共通ライフサイクルスキル標準）の将来スコープを反映する。

## 制約の棚卸し（最初にやる）

| 分類 | 制約 | 影響 |
|---|---|---|
| 組織 | 開発リソースは実質1名（hide、個人開発） | Should/Could の実装は逐次。網羅より正確さを優先 |
| 技術 | Claude Code と Antigravity 2.0 の2プラットフォーム両対応が必須 | 全コンポーネントで仕様差を明示する義務。片側完結は不可 |
| 技術 | Antigravity 2.0 の一次情報は実測（`docs/調査報告/01.Antigravity/` が正） | Gemini 生成の解説文書を仕様の根拠にできない |
| 技術 | 各スキルは自己完結（フォルダ単位でコピーされる、AGENTS.md 規約） | スキル間で references/ を相対参照しない。連携はスキル名の言及で行う |
| 組織 | skill-creator プラグインがスキル本体の作成・検証・テスト・最適化・配置の正 | plugin-creator はスキルの「同梱の作法」までで、実作業は委譲 |
| 規制 | 認証情報の読取・出力禁止等の AGENTS.md ガードレール | 生成物・ガイドがガードレールに違反しないこと |

**スコープ項目は上記制約に違反してはならない。**

## MoSCoW（帯域分け）

### Must（なければ成立しない）

- プラグイン**ディレクトリ構造 / plugin.json マニフェスト / 自動発見 / `${CLAUDE_PLUGIN_ROOT}`** のガイド（plugin-structure）— 両プラットフォーム対応
- **コマンド**作成ガイド（plugin-commands、Antigravity ではスキルへ変換される扱いを含む）
- **スキル同梱**の考慮事項ガイド（plugin-skills、実作業は skill-creator へ誘導）
- **2つのマニフェスト**（`.claude-plugin/plugin.json` と `plugin.json`）を同値に保つ規約への準拠
- **create-plugin コマンド**による発見 → 設計 → 実装 → 検証ワークフロー
- **plugin-validator エージェント**による構造・マニフェスト検証

### Should（価値は高いが期限が滑るなら外せる）

- **エージェント**作成ガイド（plugin-agents）と agent-creator エージェント
- **フック**作成ガイド（plugin-hooks、全フックイベント網羅）
- **MCP** 統合ガイド（plugin-mcp、stdio/SSE/HTTP/WebSocket）
- **設定管理**ガイド（plugin-settings、`.local.md` パターン）

### Could（あれば嬉しい磨き込み）

- **共通ライフサイクルスキル標準** reference（SI-CORE-006）: `<plugin>:init` / `doctor` / `update` / `uninstall` の標準仕様 reference と雛形の同梱
- **依存関係管理** ガイド（マニフェスト `metadata.dependencies` の宣言と検証、SI-CORE-006 4-3）
- スクリプト化できる定型処理を references/ でなく scripts/ に置く設計チェック項目化（SI-CORE-006 4-2）

### Won't（今回は明示的に延期・除外）

| Won't 項目 | なぜやらないか |
|---|---|
| **スキル本体（SKILL.md）の作成・検証・テスト・最適化・配置の実作業** | skill-creator プラグインが正。責務を混ぜると保守が破綻する（Value「責務分離」） |
| **プラグインのホスティング / マーケットプレイス配信インフラ** | マーケットプレイス定義は BitzSkills ルート（`marketplace.json`）と各プラットフォーム CLI の責務 |
| **GUI / ノーコードのプラグインビルダー** | 対象は Claude Code / Antigravity を使うエンジニア。反ターゲットに投資しない |
| **Claude Code / Antigravity 以外のプラットフォーム対応**（他 AI ツールのプラグイン機構） | 両対応の正確さを最優先。対象拡大は仕様差保守を破綻させる |
| **バージョン bump / リリース検証スクリプトの提供** | `scripts/bump_version.py` / `release_check.py`（リポジトリ共用）が正。重複実装しない |
| **プラグインの自動生成（対話なしの全自動スキャフォールド）** | create-plugin は「確認の質問をする」ガイド付き。仮定で作らない設計思想に反する |

## In-Scope / Out-of-Scope 境界（必須）

| 項目 | In / Out | 補足 |
|---|---|---|
| プラグイン構造・マニフェスト・自動発見の設計支援 | **In** | plugin-structure |
| コマンド / エージェント / フック / MCP / 設定 / スキル同梱の各設計支援 | **In** | コンポーネント別6スキル |
| プラグイン構造・マニフェストの機械検証 | **In** | plugin-validator |
| 両プラットフォーム仕様差の一次情報保守 | **In** | 全スキルの横断責務 |
| 共通ライフサイクルスキル標準の reference 化 | **In（Could / 将来 = SI-CORE-006）** | 標準名 init/doctor/update/uninstall |
| スキル本体の作成・検証・配置の実作業 | **Out** | skill-creator が正 |
| リリース検証 / version bump スクリプト | **Out** | リポジトリ共用 scripts が正 |
| ホスティング / 配信インフラ | **Out** | プラットフォーム CLI・marketplace の責務 |
| 非 Claude Code / 非 Antigravity プラットフォーム | **Out** | 対象外 |
