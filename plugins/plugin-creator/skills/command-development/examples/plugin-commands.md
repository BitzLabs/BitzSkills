# プラグインコマンドの例集

プラグイン固有のパターンと機能を使うコマンドの実例。

## 1. シンプルなプラグインコマンド

**用途:** プラグインスクリプトを使う基本コマンド

```markdown
---
description: プラグインツールでコード品質を分析する
argument-hint: [file-path]
allowed-tools: Bash(node:*), Read
---

@$1 をプラグインの品質チェッカーで分析する:

!`node ${CLAUDE_PLUGIN_ROOT}/scripts/quality-check.js $1`

分析出力をレビューし、所見の要約・優先して対処すべき問題・改善提案・
品質スコアの解釈を提示する。
```

**ポイント:** `${CLAUDE_PLUGIN_ROOT}` によるポータブルなパス、
ファイル参照とスクリプト実行の組み合わせ、単一目的。

## 2. スクリプトベースの分析

**用途:** 複数のプラグインスクリプトで包括的な監査を行う

```markdown
---
description: プラグイン一式でコードを総合監査する
argument-hint: [directory]
allowed-tools: Bash(*)
model: sonnet
---

$1 の総合監査を実行する:

**セキュリティスキャン:**
!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/security-scan.sh $1`

**パフォーマンス分析:**
!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/perf-analyze.sh $1`

**ベストプラクティスチェック:**
!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/best-practices.sh $1`

全結果を分析し、緊急対応が必要な問題・最適化の機会・脆弱性と修正・
総合的な健全性スコアを含むレポートを作成する。
```

## 3. テンプレートベースの生成

```markdown
---
description: テンプレートからAPIドキュメントを生成する
argument-hint: [api-file]
---

テンプレート構造: @${CLAUDE_PLUGIN_ROOT}/templates/api-documentation.md

API実装: @$1

上記テンプレートの形式に従って完全なAPIドキュメントを生成する。

含める内容: HTTPメソッド付きエンドポイント説明・リクエスト/レスポンス
スキーマ・認証要件・エラーコード・curlによる使用例・レート制限情報。
```

## 4. 複数スクリプトのワークフロー

```markdown
---
description: リリースワークフロー一式を実行する
argument-hint: [version]
allowed-tools: Bash(*), Read
---

バージョン $1 のリリースワークフローを実行する:

**Step 1 - リリース前検証:**
!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/pre-release-check.sh $1`

**Step 2 - 成果物のビルド:**
!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/build-release.sh $1`

**Step 3 - テストスイート実行:**
!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/run-tests.sh`

**Step 4 - パッケージング:**
!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/package.sh $1`

全ステップの出力を確認し、失敗や警告・成果物の場所・テスト結果の要約・
デプロイへの次のステップ・必要ならロールバック計画を報告する。
```

## 5. 設定駆動のデプロイ

```markdown
---
description: 環境設定を使ってアプリをデプロイする
argument-hint: [environment]
allowed-tools: Read, Bash(*)
---

$1 用のデプロイ設定: @${CLAUDE_PLUGIN_ROOT}/config/$1-deploy.json

現在のgit状態: !`git rev-parse --short HEAD`

ビルド情報: !`cat package.json | grep -E '(name|version)'`

上記設定を使って $1 環境へのデプロイを実行する。

チェックリスト: 設定の検証 → ビルド → デプロイ前テスト → デプロイ →
スモークテスト → 成功確認 → デプロイログ更新。
```

## 6. エージェント統合

```markdown
---
description: プラグインエージェントで詳細なコードレビューを行う
argument-hint: [file-or-directory]
---

@$1 の包括的コードレビューを code-reviewer エージェントで開始する。

エージェントが行うこと:
1. **静的解析** — コードスメルとアンチパターンの検出
2. **セキュリティ監査** — 潜在的な脆弱性の特定
3. **パフォーマンスレビュー** — 最適化機会の発見
4. **ベストプラクティス** — 規約への準拠確認
5. **ドキュメントチェック** — ドキュメントの十分さ確認

エージェントがアクセスできるリソース:
- リントルール: ${CLAUDE_PLUGIN_ROOT}/config/lint-rules.json
- セキュリティチェックリスト: ${CLAUDE_PLUGIN_ROOT}/checklists/security.md

注: Task ツールでプラグインの code-reviewer エージェントを起動する。
```

## 7. スキル統合

```markdown
---
description: プラグイン標準に従ってAPIをドキュメント化する
argument-hint: [api-file]
---

APIソースコード: @$1

api-documentation-standards スキルを使って、以下を満たすAPIドキュメントを
生成する:
- **OpenAPI準拠** — OpenAPI 3.0 仕様に従う
- **一貫した書式** — プラグインのドキュメントスタイルを使う
- **完全なカバレッジ** — 全エンドポイントとスキーマを網羅する
- **質の高い例** — 現実的な使用例を提供する
- **エラーの文書化** — 全エラーシナリオをカバーする
```

スキル名への言及で Claude にスキルの読み込みを促す。

## 8. 複数コンポーネントのワークフロー

```markdown
---
description: 全プラグインコンポーネントを使う包括的レビュー
argument-hint: [file-path]
allowed-tools: Bash(node:*), Read
---

対象ファイル: @$1

**Phase 1: 自動分析**
プラグインアナライザを実行: !`node ${CLAUDE_PLUGIN_ROOT}/scripts/analyze.js $1`

**Phase 2: 詳細レビュー（エージェント）**
code-quality-reviewer エージェントを起動し、構造・エラー処理・
テストカバレッジ・ドキュメント品質を精査する。

**Phase 3: 規約チェック（スキル）**
coding-standards スキルで命名規則・書式・ベストプラクティスを検証する。

**Phase 4: レポート生成**
テンプレート: @${CLAUDE_PLUGIN_ROOT}/templates/review-report.md
全所見をテンプレートに従ってまとめる。

**Phase 5: 提言**
優先度付きのアクション（必須修正 / 推奨改善 / あれば良い強化）を、
ファイル位置と具体的な変更案付きで生成する。
```

## 9. 入力検証付きコマンド

```markdown
---
description: 検証付きで環境向けビルドを行う
argument-hint: [environment]
allowed-tools: Bash(*)
---

環境引数の検証: !`echo "$1" | grep -E "^(dev|staging|prod)$" && echo "VALID" || echo "INVALID"`

ビルドスクリプト確認: !`test -x ${CLAUDE_PLUGIN_ROOT}/scripts/build.sh && echo "EXISTS" || echo "MISSING"`

設定ファイル確認: !`test -f ${CLAUDE_PLUGIN_ROOT}/config/$1.json && echo "FOUND" || echo "NOT_FOUND"`

全検証がパスしたら:

**設定:** @${CLAUDE_PLUGIN_ROOT}/config/$1.json
**ビルド実行:** !`bash ${CLAUDE_PLUGIN_ROOT}/scripts/build.sh $1 2>&1`

検証に失敗したら: どの検証が失敗したか・期待される値/場所・修正方法・
トラブルシューティング手順を説明する。
```

## 10. 環境対応コマンド

```markdown
---
description: 環境に応じたチェックを実行する
argument-hint: [environment]
allowed-tools: Bash(*), Read
---

環境: $1

環境設定を読み込む: @${CLAUDE_PLUGIN_ROOT}/config/$1-checks.json

チェックレベルの判定: !`echo "$1" | grep -E "^prod$" && echo "FULL" || echo "BASIC"`

**本番環境の場合:**
フルテスト・セキュリティスキャン・パフォーマンス監査・コンプライアンス
チェックをすべて実行する。

**非本番環境の場合:**
基本テストとクイックリントのみ実行する。

判定基準: 本番は重大問題ゼロ必須 / staging は重大問題なし（警告は許容）/
開発はブロッカーのみ注視。続行/ブロックの判断を報告する。
```

## パターンまとめ

| パターン | 書き方 |
| --- | --- |
| スクリプト実行 | `` !`node ${CLAUDE_PLUGIN_ROOT}/scripts/name.js $1` `` |
| 設定読み込み | `@${CLAUDE_PLUGIN_ROOT}/config/name.json` |
| テンプレート利用 | `@${CLAUDE_PLUGIN_ROOT}/templates/name.md` |
| エージェント起動 | 「[agent-name] エージェントで [タスク] を行う」 |
| スキル参照 | 「[skill-name] スキルを使って [要件] を満たす」 |
| 入力検証 | `` !`echo "$1" | grep -E "^pattern$" && echo OK || echo ERROR` `` |
| リソース検証 | `` !`test -f ${CLAUDE_PLUGIN_ROOT}/path && echo YES || echo NO` `` |

## 開発のコツ

### テスト方法

1. プラグインを導入した状態でコマンドを実行する
2. `${CLAUDE_PLUGIN_ROOT}` の展開をデバッグ出力で確認する
   （`` !`echo "Plugin root: ${CLAUDE_PLUGIN_ROOT}"` ``）
3. 異なる作業ディレクトリから実行して動作を確認する
4. プラグインリソースの存在を確認する

### 避けるべき間違い

1. **相対パスの使用**: `./scripts/analyze.js` ではなく
   `${CLAUDE_PLUGIN_ROOT}/scripts/analyze.js`
2. **allowed-tools の指定漏れ**: bash実行には Bash の許可が必要
3. **入力の未検証**: 環境名などは正規表現で検証してから使う
4. **パスのハードコード**: `/home/user/.claude/plugins/...` は
   他の環境で壊れる
