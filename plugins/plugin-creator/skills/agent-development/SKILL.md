---
name: agent-development
description: Claude Codeプラグインのサブエージェント（agents/*.md）の作成を支援する。「エージェントを作りたい」「サブエージェントを追加したい」「エージェントのfrontmatter」「エージェントの例」「自律エージェント」と言われたときや、エージェント構造・システムプロンプト設計・トリガー条件の指針が必要なときに使用する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-05"
---

# agent-development

## 目的

エージェント（サブエージェント）は、複雑な複数ステップのタスクを自律的に
処理するサブプロセスである。構造・トリガー条件・システムプロンプト設計を
理解することで、強力な自律機能を作れる。

**中心概念:**

- エージェントは**自律的な作業**用、コマンドは**ユーザー起点の操作**用
- YAML frontmatter 付きマークダウンファイル
- `description` フィールド（example付き）でトリガーを定義
- 本文がシステムプロンプトになる

## ファイル構造

```markdown
---
name: agent-identifier
description: [トリガー条件]のときにこのエージェントを使用する。例:

<example>
Context: [状況の説明]
user: "[ユーザーの発話]"
assistant: "[アシスタントの応答とエージェントの使い方]"
<commentary>
[なぜこのエージェントがトリガーされるべきか]
</commentary>
</example>

model: inherit
color: blue
tools: ["Read", "Write", "Grep"]
---

あなたは[エージェントの役割]です...

**中心的な責務:**
1. [責務1]
2. [責務2]

**分析プロセス:**
[段階的なワークフロー]

**出力形式:**
[何を返すか]
```

## frontmatter フィールド

| フィールド | 必須 | 形式 | 例 |
| --- | --- | --- | --- |
| `name` | 必須 | 英小文字・数字・ハイフン、3〜50文字 | `code-reviewer` |
| `description` | 必須 | トリガー条件 + `<example>` ブロック | 下記参照 |
| `model` | 必須 | `inherit` / `sonnet` / `opus` / `haiku` | `inherit` |
| `color` | 必須 | `blue` / `cyan` / `green` / `yellow` / `magenta` / `red` | `blue` |
| `tools` | 任意 | ツール名の配列（省略時は全ツール） | `["Read", "Grep"]` |

### name

- 3〜50文字、英小文字・数字・ハイフンのみ、先頭末尾は英数字
- ✅ `code-reviewer`, `test-generator` / ❌ `helper`（汎用的すぎ）,
  `-agent-`, `my_agent`, `ag`（短すぎ）

### description（最重要フィールド）

Claude がこのエージェントをいつ起動するかを決める唯一の材料。

**必ず含めるもの:**

1. トリガー条件（「〜のときにこのエージェントを使用する」）
2. 複数の `<example>` ブロック（Context / user / assistant を含む）
3. 各例に `<commentary>`（なぜトリガーされるか）

**ベストプラクティス**: 具体例を2〜4個。能動的（proactive）と受動的
（reactive）両方のトリガーを示す。同じ意図の異なる言い回しをカバーする。
使うべきで**ない**場面も明記する。

### model

特定モデルの能力が必要な場合を除き `inherit`（親と同じモデル）を推奨。

### color

同じプラグイン内のエージェントは色を分ける。目安:
blue/cyan = 分析・レビュー、green = 生成・成功系、yellow = 検証・注意、
red = 重大・セキュリティ、magenta = 創造・生成。

### tools

最小権限の原則で絞る。よく使う組み合わせ:

- 読み取り専用分析: `["Read", "Grep", "Glob"]`
- コード生成: `["Read", "Write", "Grep"]`
- テスト: `["Read", "Bash", "Grep"]`

## システムプロンプト設計

本文がエージェントのシステムプロンプトになる。**二人称**でエージェントに
直接語りかける形で書く（コマンドやスキルの記述スタイルとは異なる点に注意）。

### 標準テンプレート

```markdown
あなたは[ドメイン]を専門とする[役割]です。

**中心的な責務:**
1. [主要な責務]
2. [副次的な責務]

**分析プロセス:**
1. [ステップ1]
2. [ステップ2]

**品質基準:**
- [基準1]
- [基準2]

**出力形式:**
以下の形式で結果を提示する:
- [含める内容]
- [構造]

**エッジケース:**
- [ケース1]: [対処法]
- [ケース2]: [対処法]
```

### ルール

- ✅ 二人称で書く（「あなたは〜」）、責務を具体的に、プロセスを段階的に、
  出力形式を定義、品質基準とエッジケースを含める、10,000文字未満
- ❌ 一人称（「私は〜」）、曖昧・汎用的な記述、プロセスの省略、
  出力形式の未定義

## 作成方法

### 方法1: AI支援生成

Claude Code 本体から抽出されたプロンプトパターンを使う:

```
次の要望に基づいてエージェント設定を作成する: "[要望の説明]"

要件:
1. 中心的な意図と責務を抽出する
2. そのドメインの専門家ペルソナを設計する
3. 包括的なシステムプロンプトを作成する
   （行動境界・具体的な方法論・エッジケース処理・出力形式）
4. 識別子を作成する（英小文字・ハイフン・3〜50文字）
5. トリガー条件付きの description を書く
6. 使用場面を示す <example> ブロックを2〜3個含める

JSON で返す:
{
  "identifier": "agent-name",
  "whenToUse": "〜のときに使用する。例: <example>...</example>",
  "systemPrompt": "あなたは..."
}
```

完全なテンプレートは `examples/agent-creation-prompt.md`、
元のシステムプロンプトは `references/agent-creation-system-prompt.md` を参照。
本プラグインの `agent-creator` エージェントもこの方法を実装している。

### 方法2: 手動作成

1. 識別子を決める（3〜50文字・英小文字・ハイフン）
2. example 付きの description を書く
3. model（通常 `inherit`）と color を選ぶ
4. 必要なら tools を絞る
5. 上記テンプレートでシステムプロンプトを書く
6. `agents/agent-name.md` として保存する

## バリデーション

- **name**: 3〜50文字・英小文字・数字・ハイフン・先頭末尾英数字
- **description**: 10〜5,000文字（推奨200〜1,000文字 + example 2〜4個）。
  トリガー条件と example を必ず含む
- **システムプロンプト**: 20〜10,000文字（推奨500〜3,000文字）。
  責務・プロセス・出力形式が明確

`scripts/validate-agent.sh` で構造を自動検証できる。

## テスト

**トリガーのテスト**: description の example に近い言い回しで話しかけ、
エージェントが起動するか確認する。

**システムプロンプトのテスト**: 典型的なタスクを与え、プロセスに従うか・
出力形式が正しいか・エッジケースを処理するかを確認する。

## 追加リソース

### リファレンス

- **`references/system-prompt-design.md`** — システムプロンプトの設計パターン全集
- **`references/triggering-examples.md`** — example の書式とベストプラクティス
- **`references/agent-creation-system-prompt.md`** — Claude Code 由来の生成プロンプト

### 実例

- **`examples/agent-creation-prompt.md`** — AI支援生成のテンプレート
- **`examples/complete-agent-examples.md`** — 用途別の完全なエージェント例

### スクリプト

- **`scripts/validate-agent.sh`** — エージェントファイルの構造検証

## 作成ワークフロー

1. エージェントの目的とトリガー条件を定義する
2. 作成方法（AI支援 / 手動）を選ぶ
3. `agents/agent-name.md` を作成する
4. 必須フィールドをすべて含む frontmatter を書く
5. ベストプラクティスに従ってシステムプロンプトを書く
6. description に 2〜4個のトリガー example を含める
7. `scripts/validate-agent.sh` で検証する
8. 実際のシナリオでトリガーをテストする
9. プラグインの README にエージェントを記載する
