# 標準プラグインの例

コマンド・エージェント・スキル・フックを備えた、配布に耐える構成のプラグイン。

## ディレクトリ構造

```
code-quality/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   ├── lint.md
│   ├── test.md
│   └── review.md
├── agents/
│   ├── code-reviewer.md
│   └── test-generator.md
├── skills/
│   ├── code-standards/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── style-guide.md
│   └── testing-patterns/
│       ├── SKILL.md
│       └── examples/
│           ├── unit-test.js
│           └── integration-test.js
├── hooks/
│   ├── hooks.json
│   └── scripts/
│       └── validate-commit.sh
└── scripts/
    ├── run-linter.sh
    └── generate-report.py
```

## ファイル内容（抜粋）

### .claude-plugin/plugin.json

```json
{
  "name": "code-quality",
  "version": "1.0.0",
  "description": "リント・テスト・レビュー自動化を含む総合的なコード品質ツール",
  "author": { "name": "Quality Team", "email": "quality@example.com" },
  "homepage": "https://docs.example.com/plugins/code-quality",
  "repository": "https://github.com/example/code-quality-plugin",
  "license": "MIT",
  "keywords": ["code-quality", "linting", "testing", "code-review"]
}
```

### commands/lint.md

```markdown
---
name: lint
description: コードベースにリントチェックを実行する
---

# lint コマンド

プロジェクトのコードベースに包括的なリントチェックを実行する。

## 手順

1. プロジェクト種別と導入済みリンターを検出する
2. 適切なリンター（ESLint / Pylint / RuboCop 等）を実行する
3. 結果を収集・整形する
4. ファイル位置と重大度付きで問題を報告する

## 実装

リントスクリプトを実行する:

    bash ${CLAUDE_PLUGIN_ROOT}/scripts/run-linter.sh

出力をパースし、以下の分類で提示する:
- 重大な問題（修正必須）
- 警告（修正推奨）
- スタイル提案（任意）
```

### agents/code-reviewer.md

```markdown
---
description: バグ・セキュリティ問題・改善機会の特定に特化したコードレビュー専門エージェント
capabilities:
  - コードのバグ・ロジックエラーの分析
  - セキュリティ脆弱性の特定
  - パフォーマンス改善の提案
  - プロジェクト規約への準拠確認
  - テストカバレッジの妥当性レビュー
---

# code-reviewer エージェント

包括的なコードレビューを行う専門エージェント。

## レビュープロセス

1. **初回スキャン**: 明白な問題の素早い確認
2. **詳細分析**: 変更コードの行単位レビュー
3. **文脈評価**: 関連コードへの影響確認
4. **ベストプラクティス**: プロジェクト・言語標準との比較
5. **提言**: 優先度付きの改善リスト

## スキルとの連携

プロジェクト固有のガイドラインとして `code-standards` スキルを読み込む。

## 出力形式

レビューしたファイルごとに: 総合評価 / 重大な問題（マージ前修正必須）/
重要な問題（修正推奨）/ 提案 / 良かった点。
```

### skills/code-standards/SKILL.md

```markdown
---
name: code-standards
description: コードレビュー・スタイルガイド適用・命名規則チェック・品質基準の確認を行うときに使用する。プロジェクト固有のコーディング規約とベストプラクティスを提供する。
---

# code-standards

コード品質を維持するための規約集。

## スタイルガイドライン

- **インデント**: 2スペース（JS/TS）、4スペース（Python）
- **行長**: 最大100文字
- **命名**: 変数は camelCase（JS）/ snake_case（Python）、クラスは PascalCase、
  定数は UPPER_SNAKE_CASE、ファイルは kebab-case

## エラーハンドリング

- エラーを黙って握りつぶさない
- 文脈付きでログを残す
- 具体的なエラー型を使う
- 対処可能なエラーメッセージを書く

言語別の詳細は `references/style-guide.md` を参照。
```

### hooks/hooks.json

```json
{
  "PreToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "コードを変更する前に、code-standards スキルのコーディング規約（フォーマット・命名規則・ドキュメント）を満たしているか確認する。満たしていなければ改善を提案する。",
          "timeout": 30
        }
      ]
    }
  ],
  "Stop": [
    {
      "matcher": ".*",
      "hooks": [
        {
          "type": "command",
          "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate-commit.sh",
          "timeout": 45
        }
      ]
    }
  ]
}
```

### hooks/scripts/validate-commit.sh

```bash
#!/bin/bash
# タスク完了前にコード品質を検証する

set -e

# 未コミットの変更がなければ終了
if [[ -z $(git status -s) ]]; then
  echo '{"systemMessage": "検証対象の変更なし。タスク完了。"}'
  exit 0
fi

# 変更されたコードファイルを抽出
CHANGED_FILES=$(git diff --name-only --cached | grep -E '\.(js|ts|py)$' || true)

if [[ -z "$CHANGED_FILES" ]]; then
  echo '{"systemMessage": "コードファイルの変更なし。検証パス。"}'
  exit 0
fi

ISSUES=0

for file in $CHANGED_FILES; do
  case "$file" in
    *.js|*.ts)
      if ! npx eslint "$file" --quiet; then
        ISSUES=$((ISSUES + 1))
      fi
      ;;
    *.py)
      if ! python -m pylint "$file" --errors-only; then
        ISSUES=$((ISSUES + 1))
      fi
      ;;
  esac
done

if [[ $ISSUES -gt 0 ]]; then
  echo "{\"systemMessage\": \"コード品質の問題が ${ISSUES} 件あります。完了前に修正してください。\"}"
  exit 1
fi

echo '{"systemMessage": "コード品質チェックをパス。コミット可能です。"}'
exit 0
```

## 使い方の例

```
$ claude
> /lint
リントチェックを実行中...

重大な問題 (2):
  src/api/users.js:45 - SQLインジェクション脆弱性
  src/utils/helpers.js:12 - 未処理のPromise rejection

> src/api/users.js の変更をレビューして

[code-reviewer エージェントが自動選択される]

重大な問題:
  1. 45行目: SQLインジェクション脆弱性
     - 文字列連結でSQLクエリを構築している
     - パラメータ化クエリに置き換える
```

## ポイント

1. **完全なマニフェスト**: 推奨メタデータをすべて記載
2. **複数コンポーネント**: コマンド・エージェント・スキル・フックの連携
3. **リッチなスキル**: references / examples で詳細を分離
4. **自動化**: フックで規約を自動的に強制
5. **一貫性**: コンポーネント同士が協調して動く

## このパターンが向く場面

- 配布用の本格プラグイン
- チームコラボレーションツール
- 規約の強制が必要なプラグイン
- 複数の入口を持つ複雑なワークフロー
