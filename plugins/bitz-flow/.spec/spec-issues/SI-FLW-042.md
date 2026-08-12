---
id: SI-FLW-042
raised_by: M2 設計時の実装者（claude）
target: FLW-DSN-015 の enum namespace 表・FLW-DSN-012 の正規状態写像・FLW-DSN-006 の audit 分類
proposed_change_type: modify
status: accepted
---
- **目的**: `FLW-DSN-015` が定めた「**同名語の混同を避けるため namespace を別 field で持つ**」規律を、
  M2 で扱う WorkUnit state と worktree state にも適用する。現状この2つは namespace 表に無い。

- **現状（namespace 表は5つ）**:

  | namespace | field |
  |---|---|
  | write 機械 | `write_state` |
  | operation 結果 | `result_code` |
  | intent 記録 | `intent_record_state` |
  | Gate | `gate_status` |
  | attempt | `attempt_status` |

  一方、設計には次の2つが**表に入らないまま**存在する。

  | 出所 | 状態 |
  |---|---|
  | `FLW-DSN-012` の正規状態写像 | WorkUnit state: `planned` / `isolated` / `active` / `verified` / `pr-draft` … |
  | `FLW-DSN-006` の audit 分類 | worktree state: `active-clean` / `active-dirty` / `pr-open` / `merged-exact` / `remote-advanced` / `worktree-mismatch` / `orphan` / `failed-retained` |

- **実際に起きた事故**: `write_state` は同一文書内で2通りに書かれており、
  M1-1 の契約凍結時に実装者が誤読して schema を小文字で凍結した（`SI-FLW-039` で是正）。
  **同名語の危険は既に一度現実になっている。**

  そして `planned` は現在、**WorkUnit state と `write_state` の両方に存在する**。
  M2 は worktree の状態遷移を扱い write 状態機械と隣接するため、同じ事故が起きる位置にある。

- **提案する修正**:

  1. namespace 表へ **`work_unit_state`** と **`worktree_state`** を追加し、closed enum を宣言する。
  2. `write_state` と同じく**大文字スネーク**へ表記を統一するか、あるいは
     「この2つは小文字 kebab を正とする」と明示する。**どちらでもよいが、決めて書く**ことが要点。
     `worktree_state` は `active-clean` のようにハイフンを含む語が自然なため、
     大文字スネーク化（`ACTIVE_CLEAN`）が読みにくくなる可能性がある。
  3. `planned` のように複数 namespace に現れる語を**一覧として明示**し、
     読み手が「どの namespace の planned か」を必ず意識できるようにする。

- **対象ファイル**:
  - `.spec/design/FLW-DSN-015.md`（enum namespace 表）
  - `.spec/design/FLW-DSN-012.md`（正規状態写像）
  - `.spec/design/FLW-DSN-006.md`（audit 分類）
  - M2 で凍結する schema と `references/output-contract.md`

- **確認観点**: 修正後、namespace 表に7つの enum が並び、それぞれ closed enum を持つこと。
  複数 namespace に現れる語（少なくとも `planned`）が明示されていること。
  M2 の契約凍結タスクが、この表を正として schema を作れること。

- **影響推定・ロールバック**: 設計文書と M2 で新規に作る schema の話であり、
  M0 / M1 で凍結済みの5 namespace は変えない。ロールバックは追加分を除くだけで足りる。

- **依存**: `SI-FLW-039`（`write_state` の表記統一）の後続。M2 の契約凍結より前に裁定したい。
