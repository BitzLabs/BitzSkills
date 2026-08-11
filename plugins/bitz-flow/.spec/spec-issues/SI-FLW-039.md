---
id: SI-FLW-039
raised_by: M1-3 着手時の実装者（claude）
target: FLW-DSN-015（write状態機械の不変条件表と本文）
proposed_change_type: modify
status: accepted
---
- **目的**: `write_state` の表記が同一設計文書内で2通りあり、実装が誤った側を採る事故が実際に
  起きたため、正となる表記へ統一する。

- **現状（同一文書内の不一致）**:

  | 箇所 | 表記 | 位置づけ |
  |---|---|---|
  | 状態機械の不変条件表 | `planned` / `guarded` / `pending-intent` …（小文字 kebab） | 説明的な記述 |
  | enum namespace 表 | `PLANNED, GUARDED, PENDING_INTENT, …`（大文字スネーク） | **closed enum の宣言** |

  recovery matrix の code 列は `PENDING_INTENT`（大文字）を使っており、
  他の4 namespace（`result_code` / `intent_record_state` / `gate_status` / `attempt_status`）も
  すべて大文字スネークである。

- **実際に起きた事故**: M1-1 の契約凍結時、実装者が説明的な小文字表記を enum の正と誤読し、
  `schemas/result-v1.schema.json` の `write_state` を小文字 kebab で凍結した。
  M1-3 着手時に発見し、closed enum の宣言（大文字スネーク）へ是正した。
  同時に `references/output-contract.md` と `flowlib/recovery.py` の
  `project_write_state` も是正済みで、write は未公開のため外部影響は無い。

- **提案する修正**: 不変条件表の小文字 kebab 表記を、closed enum の宣言に合わせて
  大文字スネークへ統一する。本文中の `` `pending-intent` `` も同様。
  あわせて「enum 値の正は namespace 表であり、他箇所の表記は説明である」旨を
  一文で明示し、同種の誤読を防ぐ。

- **対象ファイル**: `.spec/design/FLW-DSN-015.md`（状態機械の不変条件表、および本文の該当箇所）

- **確認観点**: 修正後、設計文書内に小文字 kebab の `write_state` 値が残らないこと。
  `schemas/result-v1.schema.json` の enum と設計の宣言が一致すること
  （`tests/test_flow_m1_core.py` の namespace 照合が機械検証する）。

- **影響推定・ロールバック**: 設計文書の表記のみの修正で、実装側は是正済み。
  requirements への影響は無い（`FLW-FR-013` / `FLW-NFR-011` / `FLW-NFR-012` は
  `write_state` の具体値を EARS に含まない）。ロールバックは文書を戻すだけで足りる。

- **依存**: なし。M1-3 以降の write 実装は是正後の大文字スネークを前提に進めている。
