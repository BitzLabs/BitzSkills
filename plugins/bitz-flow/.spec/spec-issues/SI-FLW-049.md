---
id: SI-FLW-049
raised_by: FLW-REV-013（独立5観点レビュー・FAIL 2.31）
target: FLW-DSN-012・FLW-DSN-016・FLW-DSN-014
proposed_change_type: modify
status: open
---
- **目的**: **operation class の所有権を1文書に確定する。** 現在2つの設計文書が同じ
  operation に別の class を宣言しており、その差が **M2 出口で公開される operation 集合**を
  実質的に変えている。

- **確認済みの欠陥**（`FLW-REV-013:SYN-009` / `SYN-010` / `SYN-017`。
  2026-08-13 に3文書を突合して機械確認）:

  `FLW-DSN-012.md:26` は class の語彙を定義する（**この文書が operation 契約の正**）:

  ```
  class = read / local-write / remote-write / destructive
  ```

  同 `:51,54,55` の宣言:

  | operation | class | 承認 | recovery |
  |---|---|---|---|
  | `worktree.finish` | **destructive** | `explicit-human` | `REC-WORKTREE-FINISH`（reconcile-first） |
  | `worktree.discard` | **destructive** | `explicit-human` | `REC-WORKTREE-DISCARD`（**manual-only**） |
  | `git.delete-remote-branch` | **destructive** | `explicit-human` | `REC-REMOTE-DELETE` |

  これに対し `FLW-DSN-016.md:50-51` の M2 operation catalog:

  | operation | class | 承認欄 |
  |---|---|---|
  | `worktree.finish` | **`local-write`** | **列そのものが無い** |
  | `worktree.discard` | **`local-write`** | **列そのものが無い** |
  | `git.delete-remote-branch` | `remote-write` | 同上 |

  **これは表記の相違ではなく、安全境界の変更である。** `FLW-DSN-014` の write class 表は
  **local-write を M2 出口で公開する**（remote-write は M3 へ送る）と定めている。
  したがってこの降格により、**recovery が `manual-only` の破壊的 operation が
  M2 出口の公開集合へ移動している**。降格の理由は `FLW-DSN-016` のどこにも記されていない。

- **併発する欠陥**:

  1. **削除する local branch の tip OID 保全規定が無い**（`SYN-010`）。
     `discard` / `finish` はいずれも local branch を削除するが、削除前の tip OID を
     保全する規定が無いため、**未 push の commit が gc で恒久喪失する**。
     `destructive` に戻すなら、その要件として保全を課すのが自然である。
  2. **recovery 識別子が2系統に分裂している**（`SYN-017`）。
     `REC-WT-*` は `FLW-DSN-016` のみ、`REC-WORKTREE-*` は `FLW-DSN-012` / `013` に存在。
     移行も別名定義もされていない。さらに **`REC-WT-RESUME` はどこにも定義が無い**。

- **提案する修正**（**選択肢を提示し、裁定を求める**）:

  | 案 | 内容 | 評価 |
  |---|---|---|
  | **案A** | **`FLW-DSN-012` を class の唯一の正とし、`FLW-DSN-016` から class 列を削除する**（参照に置換） | **推奨。** 二重定義そのものを無くす。`FLW-DSN-016` は M2 固有の詳細（guard target・step）に専念できる |
  | 案B | class 体系を再設計し、両文書を同時に改訂する。`destructive` を「local-destructive / remote-destructive」へ分割し、M2 出口の公開可否を class から導出できるようにする | 表現力は上がるが、M0 / M1 で確定済みの契約に破壊的変更が及ぶ |
  | 案C | `FLW-DSN-016` の降格を追認し、`FLW-DSN-012` を書き換える | **非推奨。** 降格の技術的根拠が示されておらず、安全境界を緩める方向の変更を無記録で行うことになる |

  **推奨は案A。** そのうえで、裁定に伴い次を確定する:

  - `destructive` の承認要件（`explicit-human`）が M2 の承認 capability 機構と
    どう対応するか（capability による単回承認は `explicit-human` を満たすか）
  - **M2 出口で公開する operation 集合**（`destructive` を含めるか否か）。
    含めない場合、M2 出口の意味（worktree-first の安全境界が閉じたと言えるか）を再定義する
  - **削除する branch tip OID の保全規定**（保全先・保持期間・参照方法）
  - recovery 識別子を `REC-WORKTREE-*` へ統一し、`REC-WT-RESUME` に対応する
    `resume` の recovery を定義する

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-012.md`（class 語彙・operation 契約表・recovery 表）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`（§1 operation catalog・§8 recovery matrix）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（write class 表・M2 出口条件）

- **確認観点**:
  - 同一 operation の class が全文書で一致すること（機械検査。`SI-FLW-052` に含める）
  - `REC-*` 識別子が**すべて定義を持つ**こと（現在 `REC-WT-RESUME` が未定義）
  - M2 出口で公開する operation 集合が、class から機械的に導出できること
  - branch 削除前の tip OID が復元可能な形で保全されること

- **影響推定・ロールバック**: 案A なら `FLW-DSN-016` の表1列の削除と参照追記で済む。
  M2 出口の公開集合を変える場合は `FLW-DSN-014` の縮退規則3 の解除条件に波及する。
  未実装のため文書改訂のみで戻せる。

- **依存**: `SI-FLW-048`（案A で `sync-main` を独立 operation にする場合、その class を
  本 issue の体系で決める）。`SI-FLW-051`（M2 出口条件を変える場合に連動）。
