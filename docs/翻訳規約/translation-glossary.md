# nexus-architect 日本語翻訳ルール（用語集・スタイルガイド）

このファイルは nexus-architect リポジトリの Markdown ドキュメントを英語から日本語へ翻訳する際に、
全バッチで一貫して適用する規約です。翻訳作業者（Antigravity/Gemini）は必ず遵守してください。

## 基本方針

1. **技術文書としての正確性を最優先する**。意味が曖昧になる意訳・要約はしない。原文の技術的な意味・粒度・構造（見出しレベル、表、コードブロック、Mermaid図、リスト構造）を保持したまま全文を翻訳する。
2. **コードブロック内（```で囲まれた部分）は翻訳しない**。コマンド例、コード例、ファイルパス、YAML/JSON設定はそのまま残す。ただしコードブロック内の日本語コメントとして書かれている説明文はコメントも英語のままでよい（無理に和訳しない）。
3. **見出し構造・表構造・Front Matter（YAML）のキー名は変更しない**。表のセル内容と見出しテキストのみ翻訳する。
4. Markdownのリンク構文はそのまま保持し、リンクテキストのみ翻訳する（例: `[Getting Started](docs/getting-started.md)` → `[Getting Started（はじめに）](docs/getting-started.md)`）。ファイルパスは変更しない。

## 専門用語の扱い（最重要）

- **専門用語（固有の技術用語・製品名・フレームワーク名など）は「English（日本語訳）」の形式で表記する。**
  例:
  - Bounded Context（境界づけられたコンテキスト）
  - Ubiquitous Language（ユビキタス言語）
  - Domain Storytelling（ドメインストーリーテリング）
  - Two-Phase Commit（二相コミット）
  - error budget（エラーバジェット）
  - Jobs-to-be-Done（ジョブ理論）
  - greenfield（新規開発）
  - legacy refactoring（レガシーリファクタリング）
- 同一用語が同一ファイル内で繰り返し登場する場合、**初出時のみ「English（日本語）」形式**とし、2回目以降は English 表記のみでよい（読みやすさのため）。
- **カタカナに変換しても原語の意味がほぼそのまま伝わり、かつ日本語IT文書で定着している用語は英語のままでよい**（無理に日本語を付けない）。
  例: API, SLA, SLO, SLI, NFR, FR, DDD, CRUD, JDBC, ScalarDB, Kubernetes, Terraform, Helm, Mermaid, HTAP, RTO, RPO, Spring Boot, Storybook, Atomic Design, DTCG, Plugin, Skill, Pipeline, Config, Schema, Endpoint, Repository
- **製品名・固有名詞（ScalarDB, Claude Code, Codex, GitHub, Mermaid, Spring Boot, Kubernetes, Terraform, Helm, Docker, Oracle, MySQL, PostgreSQL など）は翻訳せず英語のまま**とする。
- 動詞化した技術用語（例: "scaffold", "migrate", "review"）は文脈に応じて自然な日本語動詞句にしてよいが、対象読者が技術者であることを前提に平易化しすぎない。

## 禁止事項

- 意味を薄める意訳（例: 技術的な制約条件を「〜のようなもの」のように曖昧化する）は禁止。
- 原文にない情報の追加や、原文にある情報の省略は禁止。
- 見出し番号・箇条書きの順序・表の列順を変更しない。
- ライセンス条文（LICENSEファイル）は翻訳対象外（対象ファイルリストに含まれていない）。

## ファイル命名規約

- 翻訳元が `xxx.md` の場合、翻訳後のファイルは同じディレクトリに `xxx_ja.md` として新規作成する（原文ファイルは変更しない）。
- 翻訳元が `xxx_en.md`（research/配下など、既に英語サフィックス付き）の場合、翻訳後は同ディレクトリの `xxx_ja.md` とする（`_en` を `_ja` に置換。research/配下は既存の対応するxxx_ja.mdがあるため対象外）。
- `SKILL.md` の場合は同ディレクトリに `SKILL_ja.md` として新規作成する。
