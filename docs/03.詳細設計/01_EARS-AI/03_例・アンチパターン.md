# EARS-AI例・アンチパターン

## 1. Core例

```markdown
- [REQ-001:CONST-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 監査ログに秘密情報を出力しない。
- [REQ-001:AC-01] [ACTOR:TargetSystem] [WHEN] 利用者が保存操作を確定した場合 [MUST] [THEN] 入力データを永続化する。
- [REQ-001:AC-02] [ACTOR:TargetSystem] [IF_ERROR] 永続化に失敗した場合 [MUST] [THEN] エラーコード `SAVE-001` を返す。
```

## 2. 複数結果

悪い例:

```markdown
- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 認証に成功した場合 [MUST] [THEN] tokenを発行して監査logを記録する。
```

良い例:

```markdown
- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 認証に成功した場合 [MUST] [THEN] tokenを1件発行する。
- [REQ-001:AC-02] [ACTOR:AuthService] [WHEN] 認証に成功した場合 [MUST] [THEN] 監査logを1件記録する。
```

## 3. 実行主体の混同

承認者を`ACTOR:HumanPO`として、システムの動作を課してはならない。`ACTOR`には結果を生成する実行主体を書き、
所有者を記録する場合は`x-owners`などのプロジェクトの拡張フィールドを使う。

## 4. ID階層

`REQ-001:AC-01:R-01`のような3階層IDを使わない。発動条件を繰り返した独立規範文へ分割する。

## 5. 判定不能な表現

悪い例: `高速に応答する。`

良い例:

```markdown
- [REQ-100:CONST-01] [ACTOR:ApiService] [ALWAYS] [MUST] [CONSTRAINT] 基準負荷で応答時間p95を200ms以下にする。
```

## 6. 不透明な拡張タグ

```markdown
- [REQ-100:CONST-02] [quality:THRESHOLD="<=200ms"] [ACTOR:ApiService] [ALWAYS] [MUST] [CONSTRAINT] 基準負荷で応答時間p95を200ms以下にする。
```

Core 1.0は`quality`拡張タグを保持し、重大度`warning`の診断を返すが、閾値を検証しない。Coreだけで必要な意味が読めるよう、
拡張タグへ唯一の規範情報を隠さない。

## 7. 本文中の角括弧

悪い例:

```markdown
- [TECH-030:SPEC-01] [ACTOR:Parser] [WHEN] 入力が [x] の場合 [MUST] [THEN] 配列として解釈する。
```

良い例:

```markdown
- [TECH-030:SPEC-01] [ACTOR:Parser] [WHEN] 入力が `[x]` の場合 [MUST] [THEN] 配列として解釈する。
```

## 8. 構文と意味

構文解析器の合格は、要求の意味が正しい証拠ではない。意味は人間が確認し、実装は実行可能なテストで検証する。
