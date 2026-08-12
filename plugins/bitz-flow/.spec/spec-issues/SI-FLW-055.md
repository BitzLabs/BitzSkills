---
id: SI-FLW-055
raised_by: SI-FLW-049 の詳細確認（2026-08-13）で実ファイル突合により発見
target: FLW-DSN-012・flow-core/references/operation-catalog.md
proposed_change_type: modify
status: accepted
---
- **目的**: **設計 SSOT（`FLW-DSN-012`）と出荷済み operation catalog の
  `approval` / `retry` 宣言の食い違いを解消し、両者を機械照合の対象に入れる。**
  現在この2文書は remote-write 2 operation について異なる契約を宣言しており、
  **どちらが正かを判定する機構が存在しない**。

- **確認済みの乖離**（2026-08-13、実ファイル突合で機械確認）:

  `FLW-DSN-012.md:41` の公開 action catalog（列: operation / class / approval /
  postcondition / retry / recovery）と、
  `plugins/bitz-flow/skills/flow-core/references/operation-catalog.md:99`
  の class / approval / retry / concurrency_key 表（列: operation / class /
  approval / retry / concurrency_key / 公開 milestone）を突合した結果:

  | operation | 項目 | `FLW-DSN-012` | 出荷済み catalog |
  |---|---|---|---|
  | `git.publish-branch` | `approval` | `external-write` | **`explicit-human`** |
  | `git.publish-branch` | `retry` | `reconcile-first` | **`manual-only`** |
  | `git.delete-remote-branch` | `retry` | `reconcile-first` | **`manual-only`** |

  `class` は両者一致（`remote-write` / `destructive`）。乖離は `approval` と `retry` に限る。

  **この2 operation は M1-4 で公開済み**（catalog の「公開 milestone」列）であり、
  未実装の設計案ではなく**出荷済み契約**である。

- **なぜ検出されなかったか**（構造的原因）:

  `tests/test_flow_m1_contract_rows.py` は **catalog ↔ 実装**を機械的に縛っている
  （`test_catalog_covers_all_m1_operations` / `test_read_operations_are_declared_read` /
  `test_local_write_operations_are_declared_local_write` /
  `test_remote_write_and_destructive_require_explicit_human` /
  `test_implementation_agrees_with_declared_approval` /
  `test_declared_recovery_ids_exist_in_implementation` ほか）。

  しかし **設計（`FLW-DSN-012`）↔ catalog を照合する検査は存在しない**。
  したがって設計側だけが取り残されても永久に沈黙する。
  これは `SI-FLW-052` が `guard_identity_kind` について指摘した
  「第4のコピーが三者照合の対象外」と**同型の構造欠陥**であり、
  同 issue の「要件層・設計層を照合対象へ含める」提案の実例にあたる。

- **提案する修正**（**選択肢を提示し、裁定を求める**）:

  **(a) どちらへ寄せるか** — 項目ごとに裁定する。

  | 項目 | 案A: catalog（実装）へ寄せる | 案B: 設計（012）へ寄せる |
  |---|---|---|
  | `git.publish-branch` の `approval` | `explicit-human`。実装・テストが既にこれを強制しており、remote への公開は人間裁定を要するという安全側の解釈 | `external-write`。`approval` 語彙は「外部書き込みの承認」区分を持つのだから publish はそこに属する、という語彙定義側の一貫性 |
  | 両 operation の `retry` | `manual-only`。remote 副作用の自動 reconcile を禁じる安全側 | `reconcile-first`。`REC-PUSH` / `REC-REMOTE-DELETE` の recovery 手順が定義されているのだから reconcile 可能 |

  **推奨は両項目とも案A（catalog へ寄せる）。** 実装とテストが既にその契約で
  出荷されており、設計側を書き換える方が影響が小さい。かつ両乖離とも
  catalog 側が**安全側**（より強い承認・自動 reconcile の禁止）であり、
  設計側へ寄せると出荷済みの安全境界を緩めることになる。

  なお `approval` について案A を採っても、`FLW-DSN-012.md:26` が定義する
  `approval` 語彙の `external-write` は `issue.publish`（`FLW-DSN-012.md:57`）ほかが
  引き続き使用するため、語彙からの値の削除は不要である。
  `approval` は class の2軸とは独立した第3の軸として維持する。

  **(b) 再発防止** — 設計の operation 契約表と出荷済み catalog を
  **`release_check.py` の三者照合へ加える**（`SI-FLW-052` の枠組みに乗せる）。
  照合対象は `operation` / `class` / `approval` / `retry` / `recovery` の5項目。
  `FLW-DSN-012` を SSOT とするか catalog を SSOT とするかは (a) の裁定に従う。

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-012.md`（公開 action catalog・`approval` 語彙）
  - `plugins/bitz-flow/skills/flow-core/references/operation-catalog.md`（(a) で案B を採る場合）
  - `scripts/release_check.py`・`tests/`（(b) の照合追加）

- **確認観点**:
  - 同一 operation の `class` / `approval` / `retry` / `recovery` が
    設計・catalog・実装の三者で一致すること（機械検査）
  - `approval` 語彙の全値に、それを使う operation が少なくとも1つ存在すること
    （未使用値の検出）
  - 出荷済み契約（M1-4 公開分）の安全境界が緩まないこと

- **影響推定・ロールバック**: 案A なら `FLW-DSN-012` の表2行の修正で済み、
  出荷済み plugin・実装・テストには一切触れない（version bump も不要）。
  案B を採ると出荷済み catalog の変更となり、M1 の compatibility key に
  `skill` が含まれるため **qualification の再実行**が必要になる。
  `scripts/release_check.py` を変更するため **全 pytest スイートの実行が必要**。

- **依存**: `SI-FLW-049`（operation class の所有権確定。本 issue と同じ表を対象とするため、
  class 体系の裁定結果に合わせて表の形が変わる）。
  `SI-FLW-052`（(b) の機械照合は同 issue の検査群に含める）。
