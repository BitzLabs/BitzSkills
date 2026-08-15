---
id: SI-FLW-057
raised_by: FLW-REV-016 M2 Exit再レビュー
target: worktree実動runtimeのmutation境界における例外分類とreconcile経路
proposed_change_type: modify
status: accepted
---

- **目的**: `FLW-REV-015:GP-001` が証明対象とした「安全核を迂回しない」を、
  M2 scope の `worktree.create` / `resume` について実際に成立させる。
  現状は副作用適用後の例外が transaction 境界を貫通し、部分適用が
  「副作用前に停止」と誤報される。

- **scope**（2026-08-15 の裁定で分割。`.spec/reports/decision-2026-08-15-si-flw-057-059.md`）:
  本 issue は **M2 分（`FLW-REV-016:SYN-003`）に限る**。
  破壊系（`SYN-002` の step 語彙統一、`SYN-010` の退避と削除の安全境界）は
  M3 へ移送し、`SI-FLW-060` として分離起票した。

- **発見した事実**:
  - `worktree_runtime.py` が module 内で `class RuntimeError(ValueError)` を定義して
    組み込み例外を遮蔽している。副作用適用ループの `except (RuntimeError, OSError)` は
    素の `ValueError` / `KeyError` を捕捉しない（plan 側の except は `ValueError` を含む）。
    receipt append 失敗時に worktree と branch は作成済み、QUARANTINED receipt なし、
    nonce は USED_PENDING 固着のまま、CLI は「副作用前に停止」を意味する `BLOCKED` を返す
    （`FLW-REV-016:SYN-003`）。
  - `SYN-002` の調査で、**`create` / `resume` には `worktree_cleanup` 側の reconcile 経路が
    そもそも存在しない**ことが判明した。`reconcile_steps` は `worktree.finish` /
    `worktree.discard` しか扱わないため、`create` / `resume` の部分適用から前進する
    公開手段が無い。これは M2 の論点であるため本 issue に含める。

- **提案する修正**:
  1. 遮蔽している例外クラスを固有名（例: `WorktreeRuntimeError`）へ改名し、
     mutation 境界の except を plan 側と同じ閉集合に揃える。
  2. receipt 永続化失敗を quarantine 確定経路へ接続し、部分適用が `BLOCKED` ではなく
     `PARTIAL` として報告されることを fault で実証する。
  3. `create` / `resume` の部分適用に対する reconcile 経路を定義する
     （step 語彙の SSOT 化そのものは `SI-FLW-060` が担う。本 issue は
     M2 scope の 2 operation が前進できる状態を作ることを目的とする）。

- **対象ファイル**: `plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py`、
  `.../worktree_cleanup.py`、`.../recovery.py`、`tests/test_flow_m2_runtime.py`、
  `plugins/bitz-flow/.spec/specs/m2-runtime/test-spec.md`

- **確認観点**:
  - mutation 中の任意の例外で、実副作用の有無と result code が一致すること。
  - nonce が USED_PENDING に固着せず quarantine へ確定すること。
  - `create` / `resume` の部分適用から前進する経路が存在し、fault で実証できること。

- **影響推定・ロールバック**: `FLW-TSK-080`（PR #259、マージ済み）の実装領域に閉じる。
  worktree operation は 2026-08-15 の裁定で未公開（`UNSUPPORTED`）であるため、
  修正による利用者影響は現時点で無い。

- **依存**: `FLW-REV-016:GP-003`。`SI-FLW-060` は本 issue の後に着手する
  （同じ `apply()` を触るため）。予算は後続の予算裁定に従う。
