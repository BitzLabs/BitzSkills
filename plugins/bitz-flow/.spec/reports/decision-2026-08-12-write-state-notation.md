# 裁定記録 — FLW-DSN-015 の write_state 表記を統一する

- **日付**: 2026-08-12
- **裁定者**: hide
- **対象**: `SI-FLW-039`

## 裁定

**提案どおり統一する** — `FLW-DSN-015` の不変条件表と本文にある小文字 kebab 表記
（`planned` / `pending-intent` 等）を、closed enum の宣言に合わせて**大文字スネーク**
（`PLANNED` / `PENDING_INTENT` 等）へ統一する。あわせて「**enum 値の正は namespace 表**であり、
他箇所の表記は説明である」ことを明示する。

## 経緯

M1-1 の契約凍結時、実装者が説明的な小文字表記を enum の正と誤読し、
`schemas/result-v1.schema.json` の `write_state` を小文字 kebab で凍結した。
M1-3 着手時に発見して是正済み（実装・schema・output-contract・`project_write_state`）。
write は未公開のため外部影響は無かった。

## この時期に行う理由

M2 は worktree の状態遷移を扱い、write 状態機械と隣接する。同じ誤読が再発しやすい位置にあるため、
M2 着手前に設計文書側を閉じる。

## 範囲

- 不変条件表と本文の小文字 kebab → 大文字スネーク
- mermaid 図のノード名（`Planned` / `PendingIntent` 等）は**図の表示ラベルとして残す**が、
  enum 値ではないことを注記する
- 実装側の変更は無い（M1-3 で是正済み）

## 確認

修正後、設計文書内に小文字 kebab の `write_state` 値が残らないこと。
`tests/test_flow_m1_core.py` の namespace 照合が引き続き PASS すること。
