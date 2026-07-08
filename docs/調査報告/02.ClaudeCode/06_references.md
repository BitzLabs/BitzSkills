# 第6章 引用・参考リンク (References)

本調査報告書の作成にあたり、以下の公式ドキュメントおよびワークスペース内の関連資材を参照しました。

---

## 6.1 公式情報ソース

- **Claude Code 開発者向け公式ドキュメント (code.claude.com)**
  - URL: [https://code.claude.com](https://code.claude.com)
  - 参照内容: CLI インストール手順、認証コマンド、CLI 起動オプション、Agent SDK の Python/TypeScript 向け API 仕様。
- **Claude Code MCP ドキュメント**
  - URL: [https://docs.claude.com/en/docs/claude-code/mcp](https://docs.claude.com/en/docs/claude-code/mcp)
  - 参照内容: Model Context Protocol (MCP) を用いた外部ツールの統合、SSE / Stdio トランスポートの設定例。
- **Model Context Protocol (MCP) 公式仕様サイト**
  - URL: [https://modelcontextprotocol.io](https://modelcontextprotocol.io)
  - 参照内容: MCP サーバースキーマ、プロトコルの基本構造およびライフサイクル。

---

## 6.2 ワークスペース内参照資材

ワークスペース内のプラグイン開発補助ツールキット `plugin-creator` および関連リファレンスドキュメントの記述を参考にしています。

- **プラグイン構成設計**
  - ファイル: [plugins/plugin-creator/README.md](file:///d:/44.BitzLabs/BitzSkills/plugins/plugin-creator/README.md)
  - 参照内容: プラットフォーム間互換表、スラッシュコマンドおよびエージェントの作成ワークフロー。
- **マニフェスト定義仕様**
  - ファイル: [plugins/plugin-creator/skills/plugin-structure/references/manifest-reference.md](file:///d:/44.BitzLabs/BitzSkills/plugins/plugin-creator/skills/plugin-structure/references/manifest-reference.md)
  - 参照内容: `plugin.json` 内の全フィールドの定義および検証パターン、Antigravity 2.0 マニフェスト仕様。
- **フック開発ガイド**
  - ファイル: [plugins/plugin-creator/skills/hook-development/SKILL.md](file:///d:/44.BitzLabs/BitzSkills/plugins/plugin-creator/skills/hook-development/SKILL.md)
  - 参照内容: 各種フックイベントのタイミング、入出力 JSON データのスキーマ構造、プロンプトベースフックの設計。
- **Antigravity フック仕様**
  - ファイル: [plugins/plugin-creator/skills/hook-development/references/antigravity-hooks.md](file:///d:/44.BitzLabs/BitzSkills/plugins/plugin-creator/skills/hook-development/references/antigravity-hooks.md)
  - 参照内容: Antigravity 2.0 における `hooks.json` の設定書式、ツール matcher、および camelCase での入出力契約。
- **MCP サーバー統合ガイド**
  - ファイル: [plugins/plugin-creator/skills/mcp-integration/SKILL.md](file:///d:/44.BitzLabs/BitzSkills/plugins/plugin-creator/skills/mcp-integration/SKILL.md)
  - 参照内容: stdio, SSE, HTTP, WebSocket トランスポート別の設定定義とツールのプレフィックス命名規則。
- **プラグイン設定管理パターン**
  - ファイル: [plugins/plugin-creator/skills/plugin-settings/SKILL.md](file:///d:/44.BitzLabs/BitzSkills/plugins/plugin-creator/skills/plugin-settings/SKILL.md)
  - 参照内容: `.claude/plugin-name.local.md` ファイルを用いた状態管理、および bash フックでの YAML frontmatter パース。
