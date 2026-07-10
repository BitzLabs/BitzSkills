# エージェントトリガー example の書き方

エージェントを確実にトリガーさせるための、description 内 `<example>`
ブロックの書き方の完全ガイド。

## example ブロックの形式

```markdown
<example>
Context: [状況の説明 — このやり取りに至った経緯]
user: "[ユーザーの発話そのもの]"
assistant: "[トリガー前に Claude が言うこと]"
<commentary>
[なぜこのシナリオでこのエージェントをトリガーすべきかの説明]
</commentary>
assistant: "[エージェントの起動 — 通常「[agent-name] エージェントで〜します」]"
</example>
```

## 良い example の構成要素

### Context（状況）

ユーザーの発話の前に何があったかを設定する。

```
✅ Context: ユーザーが新しい認証機能を実装したところ
✅ Context: ユーザーがPRを作成しレビューを求めている
✅ Context: ドキュメントなしで複数の関数を書いた後
❌ Context: ユーザーが助けを必要としている（曖昧すぎ）
❌ Context: 通常の使用（具体性なし）
```

### user（発話）

エージェントをトリガーすべき正確な言い回しを示す。
**同じ意図の異なる言い回し**を複数の example でカバーする:

```
例1: user: "コードをレビューして"
例2: user: "この実装をチェックしてもらえる？"
例3: user: "変更を見ておいて"
```

### assistant（トリガー前の応答）

エージェント起動前に Claude が言うことを示す。

### commentary（理由）

**なぜ**このエージェントがトリガーされるかの判断ロジックを説明する:

```
<commentary>
ユーザーが明示的にコードレビューを依頼したので、code-reviewer
エージェントをトリガーする。
</commentary>

<commentary>
コード実装の直後なので、品質確認のためレビューエージェントを
能動的に使う。
</commentary>
```

### assistant（起動）

標準パターン: 「[agent-name] エージェントで[何をするか]します。」

**重要**: example の中では、アシスタントが直接タスクに答えるのではなく、
Agent ツールを使う流れを示すこと。

## example の類型

### 類型1: 明示的な依頼

```markdown
<example>
Context: ユーザーが明示的にセキュリティ分析を依頼
user: "コードのセキュリティ脆弱性をチェックして"
assistant: "security-analyzer エージェントで徹底的なセキュリティレビューを行います。"
<commentary>
直接的なセキュリティ分析依頼が security-analyzer エージェントをトリガーする。
</commentary>
</example>
```

### 類型2: proactive（能動的）トリガー

明示的な依頼なしに、関連作業の後でエージェントが起動する:

```markdown
<example>
Context: ユーザーがデータベースクエリを実装したところ
user: "ユーザー検索機能を追加しました"
assistant: "いいですね。セキュリティ面をレビューします。"
<commentary>
データベースコードが書かれた。SQLインジェクション等のDB
セキュリティ問題を確認するため security-analyzer を能動的にトリガーする。
</commentary>
assistant: "security-analyzer エージェントでデータベースコードをチェックします。"
</example>
```

### 類型3: 暗黙的な依頼

ユーザーが直接言わずにニーズを示唆する:

```markdown
<example>
Context: ユーザーがコードのわかりにくさに言及
user: "このコード、ややこしくて追いにくい"
assistant: "コードの明確さを改善できます。"
<commentary>
複雑さの問題が示された。可読性向上のリファクタリングのため
code-simplifier エージェントをトリガーする。
</commentary>
assistant: "code-simplifier エージェントで改善案を出します。"
</example>
```

### 類型4: ツール使用パターン

直前のツール使用に基づいてトリガーする:

```markdown
<example>
Context: ユーザーがテストファイルを複数回編集した
user: "テストを全部更新しました"
assistant: "テストの品質を確認します。"
<commentary>
テストファイルへの複数の Edit があった。ベストプラクティス準拠を
確認するため test-quality-analyzer を能動的にトリガーする。
</commentary>
assistant: "test-quality-analyzer エージェントでテストをレビューします。"
</example>
```

## 複数 example の戦略

1. **言い回しのバリエーション**をカバーする（同じ意図の異なる表現）
2. **能動的と受動的の両方**をカバーする
3. **エッジケース**をカバーする（「大きいPRなので深いレビューを」等）

## よくある間違い

| ❌ 間違い | 問題点 | ✅ 修正 |
| --- | --- | --- |
| Context がない | 依頼に至った経緯が不明 | 状況説明を必ず入れる |
| commentary がない | なぜトリガーされるか不明 | 判断ロジックを説明する |
| エージェントが直接回答している | トリガーでなく出力を見せている | Agent ツールを使う流れを示す |
| example 同士が似すぎ | カバレッジが狭い | 類型・言い回しを変える |

## 何個書くか

- **最低2個**: 明示的な依頼 + バリエーションまたは能動的トリガー
- **推奨3〜4個**: 明示的 / 暗黙的 / 能動的 / エッジケース
- **最大6個**: それ以上は description が長くなりすぎる

## テンプレート集

### コードレビューエージェント

```markdown
<example>
Context: ユーザーが新機能を実装したところ
user: "ユーザー登録機能を追加しました"
assistant: "いいですね。コード品質をレビューします。"
<commentary>
コードが書かれたので code-reviewer エージェントを能動的にトリガーする。
</commentary>
assistant: "code-reviewer エージェントで実装を分析します。"
</example>

<example>
Context: ユーザーが明示的にレビューを依頼
user: "変更に問題がないかレビューして"
assistant: "code-reviewer エージェントで徹底レビューを行います。"
<commentary>
明示的なレビュー依頼がエージェントをトリガーする。
</commentary>
</example>
```

### テスト生成エージェント

```markdown
<example>
Context: テストなしで関数を実装した
user: "データ処理関数を追加しました"
assistant: "テストを生成しましょう。"
<commentary>
テストのない新規コード。test-generator エージェントを能動的にトリガーする。
</commentary>
assistant: "test-generator エージェントで網羅的なテストを作成します。"
</example>
```

### 検証エージェント

```markdown
<example>
Context: ユーザーがコミットの準備完了
user: "このコードをコミットします"
assistant: "先に検証します。"
<commentary>
コミット前に code-validator エージェントで能動的に検証する。
</commentary>
assistant: "code-validator エージェントで問題をチェックします。"
</example>
```

## トリガー問題のデバッグ

**トリガーされない場合**: example にユーザー発話の関連キーワードが
含まれるか、Context が実際の利用シナリオと一致するか、commentary の
ロジックが明確か、example で Agent ツールの使用を示しているかを確認。
→ 異なる言い回しの example を追加する。

**トリガーされすぎる場合**: example が広すぎ・汎用的すぎないか、
他エージェントと条件が重複していないかを確認。
→ example を具体化し、「使わない場面」を明記する。

**間違った場面でトリガーされる場合**: example が意図した用途と
一致しているかを確認し、正しいシナリオのみ示すよう修正する。

## まとめ

- ✅ 具体的な example を2〜4個 / 明示的と能動的の両方 / 明確な Context /
  commentary で理由を説明 / 言い回しを変える / Agent ツールの使用を示す
- ❌ 汎用的で曖昧な example / Context・commentary の省略 / 1類型のみ /
  起動ステップの省略 / 似た example の羅列
