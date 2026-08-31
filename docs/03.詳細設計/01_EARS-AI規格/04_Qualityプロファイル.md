# EARS-AI Quality Profile（将来候補）

## 1. 状態

- 状態: Deferred Draft
- Core 1.0: 対象外
- 導入条件: 通常のテスト設定では表現できない品質制約が複数確認されること

## 2. 目的

性能、セキュリティなどの検証条件を規範文へ関連付ける。Core 1.0では同等情報を既存テストコマンドへ
委譲し、本Profileの実装を必須にしない。

## 3. 予約語彙

| タグ | 用途 |
|---|---|
| `quality:CHECK` | 実行する検査ID |
| `quality:THRESHOLD` | 数値・単位・比較式 |
| `quality:EVIDENCE` | 証跡種別またはpath |
| `quality:SEVERITY` | `info`、`warning`、`error`、`critical` |
| `quality:LEVEL` | `L0`〜`L4` |

## 4. 制約

- Profile ValidatorはCore ASTを入力し、Markdownを再解析しない。
- LLMの評価だけを`quality:EVIDENCE`にしない。
- 閾値には単位と比較演算を必須とする。
- Profileが未導入でもCore構文と`bitz verify`は動作する。
- 例外承認はGit管理された理由で扱い、専用waiver基盤を前提にしない。

## 5. 例

```markdown
- [REQ-100:CONST-01] [quality:LEVEL=L4] [quality:CHECK=response-time-p95] [quality:THRESHOLD="<=200ms"] [quality:EVIDENCE=benchmark-report] [ACTOR:ApiService] [ALWAYS] [MUST] [CONSTRAINT] 通常負荷時の応答時間p95を200ms以下にする。
```
