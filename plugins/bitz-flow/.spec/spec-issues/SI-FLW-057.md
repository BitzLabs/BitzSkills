---
id: SI-FLW-057
raised_by: FLW-REV-016 M2 Exit再レビュー
target: worktree実動runtimeのreceipt step語彙・例外分類・退避と削除の安全境界
proposed_change_type: modify
status: open
---

- **目的**: `FLW-REV-015:GP-001` が証明対象とした「receipt prefix 収束」と
  「安全核を迂回しない」を実際に成立させる。現状は runtime が書く receipt を
  cleanup 核が解釈できず、副作用適用後の例外が transaction 境界を貫通する。

- **発見した事実**（`FLW-REV-016:SYN-002` / `SYN-003`）:
  - `worktree_runtime.MUTATING_STEPS` の finish は `git-worktree-remove` /
    `delete-local-branch`、`worktree_cleanup.FINISH_STEPS` は `verify-pr-merge` …
    `remove-worktree-dir` / `delete-local-branch` であり、**step 語彙が別集合**である。
    実 receipt の非空前置列を `reconcile_steps` へ入力すると finish / discard とも
    例外なく `INDETERMINATE` になる。prefix 収束は runtime 私有の閉じた集合内でのみ
    自明に成立している。
  - `worktree_runtime.py` が module 内で `class RuntimeError(ValueError)` を定義して
    組み込み例外を遮蔽している。副作用適用ループの `except (RuntimeError, OSError)` は
    素の `ValueError` / `KeyError` を捕捉しない（plan 側の except は `ValueError` を含む）。
    receipt append 失敗時に worktree と branch は作成済み、QUARANTINED receipt なし、
    nonce は USED_PENDING 固着のまま、CLI は「副作用前に停止」を意味する `BLOCKED` を返す。

  - `--backup-receipt` は退避の実行も検証も記録も行わない。retention ref は commit 済み tip
    だけを守るため、dirty worktree の discard で未コミット変更が失われる。さらに discard の
    `git branch -D` は retention 済み oid との再照合なしに走り、remove → delete の間に
    進んだ tip が回復不能になりうる（`FLW-REV-016:SYN-010`）。

- **提案する修正**:
  1. step 語彙を単一の SSOT に置き、runtime が書く receipt と cleanup 核が読む step 列を
     同一集合へ統一する。三者照合の機械検査を追加する。
  2. 遮蔽している例外クラスを固有名（例: `WorktreeRuntimeError`）へ改名し、
     mutation 境界の except を plan 側と同じ閉集合に揃える。
  3. receipt 永続化失敗を quarantine 確定経路へ接続し、部分適用が `BLOCKED` ではなく
     `PARTIAL` として報告されることを fault で実証する。
  4. `--backup-receipt` に退避の実行・検証・receipt 記録を実装し、`git branch -D` の直前に
     retention 済み oid との一致を再確認する。

- **対象ファイル**: `plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py`、
  `.../worktree_cleanup.py`、`.../recovery.py`、`tests/test_flow_m2_runtime.py`、
  `plugins/bitz-flow/.spec/specs/m2-runtime/test-spec.md`

- **確認観点**:
  - 全 crash 境界で実 receipt の completed 列が cleanup 核の step 列の真の前置になること。
  - mutation 中の任意の例外で、実副作用の有無と result code が一致すること。
  - nonce が USED_PENDING に固着せず quarantine へ確定すること。
  - dirty worktree の discard で未コミット変更が退避され、退避の成否が receipt に残ること。

- **影響推定・ロールバック**: `FLW-TSK-080`（PR #259、マージ済み）の実装領域に閉じる。
  M2 の公開 operation は既に出ているため、修正前後で receipt 形式が変わる場合は
  既存 receipt の移行方針を併せて決める。

- **依存**: `FLW-REV-016:GP-003`。予算は `FLW-REV-016:GP-005` の再裁定に従う。
