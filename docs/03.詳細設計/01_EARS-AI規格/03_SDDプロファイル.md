# EARS-AI SDD Profile（将来候補）

## 1. 状態

- 状態: Deferred Draft
- Core 1.0: 対象外
- 導入条件: Small Flowだけでは表現できない実例と、導入効果の測定結果があること

## 2. 目的

EARS-AI Coreへ開発フロー固有の語彙を持ち込まず、必要なプロジェクトだけがフロー、再試行、
人間確認を宣言できる拡張点を予約する。

## 3. 予約語彙

| タグ | 値 | 用途 |
|---|---|---|
| `sdd:FLOW` | `Small`, `Full`, `Spike` | 適用フロー |
| `sdd:STEP` | identifier | 現在の工程 |
| `sdd:RETRY_LIMIT` | 非負整数 | 自動再試行上限 |
| `sdd:HITL` | `required`, `optional` | 人間確認の要否 |
| `sdd:SPEC_REF` | EARS-AI ID | 関連規範文 |

## 4. 制約

- Core ASTの意味を変更しない。
- `sdd:HITL=required`を自動承認として扱わない。
- `Spike`成果物を本番へ直接反映しない。
- 再試行上限をローカルAI判断で引き上げない。
- Stage/Gate状態機械や永続run台帳を導入の前提にしない。

## 5. 例

```markdown
- [RULE-010:STEP-01] [sdd:FLOW=Small] [sdd:RETRY_LIMIT=2] [ACTOR:ImplAgent] [IF_ERROR] 対象テストが失敗した場合 [MUST] [THEN] 変更境界内で修正を再試行する。
- [RULE-010:STEP-02] [sdd:HITL=required] [ACTOR:ImplAgent] [IF_ERROR] 修復試行が上限へ達した場合 [MUST] [THEN] 実装を停止して人間へ判断を要求する。
```
