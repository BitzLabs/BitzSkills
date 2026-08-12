---
id: SI-FLW-041
raised_by: M2 設計時の実装者（claude）
target: FLW-DSN-015 の guard identity 閉集合・schemas/result-v1.schema.json・flowlib/guard.py
proposed_change_type: modify
status: accepted
---
- **目的**: `worktree.create` / `discard` が変える**3者を同一の target guard で守れる**ようにする。
  現状の guard identity は Git の ref と index だけを対象にしており、worktree の
  **directory と registry を守れない**。

- **現状（M1 で凍結した閉集合）**:

  ```text
  index | local-ref | remote-tracking-ref | fetch-head | remote-ref
  ```

  `FLW-DSN-015` は「mutation target type はこの5種の閉集合とし **raw path を key にしない**」と定める。
  この設計は「Git の ref と index を守る」ことを前提にしており、filesystem path は対象外だった。

- **M2 で足りなくなる理由**: `worktree.create` は次の**3者を同時に**変える。

  | 変更対象 | 現状の guard |
  |---|---|
  | repo 外の directory（worktree の実体） | **無い** |
  | Git の worktree registry（`common-dir/worktrees/<name>`） | **無い** |
  | local branch ref | `local-ref` で守れる |

  `FLW-DSN-006` の `orphan` state（「directory / ref / registry の**一部だけ存在**」）は、
  まさにこの3者がずれた状態である。**3者を同時に守る guard が無ければ、この state は
  「検出する」ことしかできず「防ぐ」ことができない。**
  M1 が commit で「記録なしの重複 write」を構造的に排除したのと同じ扱いを、worktree にも与えたい。

- **提案する修正**: guard identity の閉集合へ次の2種を追加する。

  | 追加する identity | canonical key の作り方 |
  |---|---|
  | `worktree-dir` | canonical common-dir identity ＋ worktree の canonical path を正規化した digest |
  | `worktree-registry` | canonical common-dir identity ＋ registry entry 名 |

  - **raw path を key にしない**という既存の規律は維持する。`worktree-dir` の key は
    canonical path を**そのまま**入れず、`local-ref` と同様に digest 化する。
    symlink・相対 path・case 差・別 clone を正規化して同一 worktree へ収束させる。
  - repo 外を指すため、**canonical path を提示して apply 前に人間承認**を要求する既存規定
    （`FLW-DSN-006`）は変えない。guard はその承認の**後**に取る。
  - 3者は canonical key の昇順で**まとめて取得**する（既存の昇順取得規約に乗る）。
    途中失敗時は逆順解放・副作用 0 で `BLOCKED`。

- **対象ファイル**:
  - `.spec/design/FLW-DSN-015.md`（guard identity の閉集合と正規化規則）
  - `plugins/bitz-flow/skills/flow-core/schemas/result-v1.schema.json`（`$defs.guard_identity_kind`）
  - `plugins/bitz-flow/skills/flow-core/schemas/intent-record-v1.schema.json`（同名 `$defs`）
  - `plugins/bitz-flow/skills/flow-core/references/output-contract.md`（namespace 表）
  - `plugins/bitz-flow/skills/flow-core/scripts/flowlib/guard.py`

- **確認観点**: 閉集合が 5 → 7 になっても既存の M1 fault fixture
  （`M1-FLT-005` / `006` / `019` / `024`）が PASS すること。
  `worktree-dir` の key が symlink / case 差 / 別 clone で同一 worktree へ収束すること。
  directory・registry・branch ref の3者を1回の `acquire` で昇順取得できること。
  `tests/test_flow_m1_core.py` の namespace 照合（schema と references の一致）が PASS すること。

- **影響推定・ロールバック**: enum の**加算**であり既存 key の意味を変えないため、
  `output-contract.md` の互換性規定（key 集合は加算のみ）に収まる。
  write は未公開のため外部影響は無い。ロールバックは追加した2種を除くだけで足りる。

- **依存**: M2 の実装（worktree operation の contract 凍結）が本件の裁定に依存する。
