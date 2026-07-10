# 出力規則

## 出力言語

出力言語はプロジェクトごとに`work/pipeline-progress.json`で設定される：
- `options.output_language`: "en"（デフォルト）または"ja"
- すべてのレポートドキュメント、分析テキスト、および説明文は設定された言語を使用する
- YAML Frontmatterのキーは出力言語に関係なく英語のままである
- MermaidのノードIDは英語のままである；ラベルは設定された言語を使用する

## YAML Frontmatter（必須）

すべての出力ファイルには以下のFrontmatterを含める必要がある：

```yaml
---
title: "Document Title"
schema_version: 1
phase: "Phase N: Category Name"
skill: skill-name
generated_at: "ISO8601"
input_files:
  - reports/XX/input-file.md
---
```

## ファイル命名規則

- **kebab-case only（ケバブケースのみ）**: `ubiquitous-language.md`（`ubiquitous_language.md`は不可）
- ディレクトリがフェーズを示すため、ファイル名にフェーズのプレフィックスは必要ない
- サフィックスの例: `-analysis.md`、`-evaluation.md`、`-design.md`、`-specs.md`

## 即時出力のルール

**重要**: 各ステップの完了時にファイルを出力すること。最後に出力をバッチ処理してはならない。

理由：
- Pipelineの中断と再開を可能にするため
- 中間成果物を可視化するため
- Skillの並列化を可能にするため

## 言語

- すべての出力ドキュメント: 設定された言語を使用する（上記の出力言語を参照）
- YAML Frontmatter: キーは英語、値は設定された言語
- Mermaidノード: 非ASCIIテキストを引用符で囲む

## ドキュメント構造

- 見出しレベルは`##`から始まる（`#`はタイトル用に予約されている）
- Mermaid図は適切な場所に配置する
- テーブルは標準のMarkdownフォーマットを使用する
- コードブロックには言語指定を含める必要がある
