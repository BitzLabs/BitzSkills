# 9. 引用・参考リンク (References)

本ドキュメントの作成にあたり、以下の公式ドキュメント、リポジトリ、コミュニティ活動を参照しました。

---

## 9.1 公式ドキュメントおよびライブラリ

* **OpenAI Codex 開発者ポータル / 公式ドキュメント**
  - [OpenAI Developers - Codex](https://developers.openai.com/codex)
  - [ChatGPT - Codex Web Interface](https://chatgpt.com/codex)
* **npm パッケージレジストリ**
  - [@openai/codex (npm)](https://www.npmjs.com/package/@openai/codex)
  - [@openai/codex-sdk (npm)](https://www.npmjs.com/package/@openai/codex-sdk)
* **PyPI パッケージレジストリ**
  - [openai-codex (PyPI)](https://pypi.org/project/openai-codex/)
* **Model Context Protocol (MCP)**
  - [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — Anthropic によって主導され、OpenAI Codex でも採用されている、AIエージェントとローカル/リモートツール間の通信用標準プロトコル。

---

## 9.2 コミュニティ・セキュリティ情報

* **コミュニティリソース**
  - [Awesome Codex CLI GitHub Repository (by RoggeOhta)](https://github.com/RoggeOhta/awesome-codex-cli) — Codex CLI 用の 150 以上のサブエージェント、プラグイン、MCPサーバーのキュレーションリスト。
  - [AGENTS.md Standard Specification](https://agents.md) — 各種 AI 開発エージェントがプロジェクトのコンテキストとルールを解釈するための、プレーンテキスト形式の標準規格。
* **安全対策に関するセキュリティレポート**
  - [VibeAudits - Malicious npm packages targeting Codex tokens](https://vibeaudits.com/) — 公式 `@openai/codex` パッケージを装った偽パッケージ（認証情報 `auth.json` の窃盗を狙うもの）に対する注意喚起。
