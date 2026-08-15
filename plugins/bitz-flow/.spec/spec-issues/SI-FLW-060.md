---
id: SI-FLW-060
raised_by: FLW-REV-016 M2 Exit再レビュー（SI-FLW-057 から M3 分を分離）
target: 破壊系 worktree（finish / discard）の receipt step 語彙と退避・削除の安全境界
proposed_change_type: modify
status: accepted
---

- **目的**: M3 へ移送された破壊系 worktree operation（`worktree.finish` / `worktree.discard`）
  について、receipt prefix 収束を実際に成立させ、退避と branch 削除の安全境界を閉じる。

- **由来**: `SI-FLW-057` の M3 分を 2026-08-15 の裁定で分離した
  （`.spec/reports/decision-2026-08-15-si-flw-057-059.md`）。
  破壊系の M3 移送は `.spec/reports/decision-2026-08-15-m0-shipping-surface-and-m2-rescope.md`。

- **発見した事実**:
  - **step 語彙の不一致**（`FLW-REV-016:SYN-002`）:
    `worktree_runtime.MUTATING_STEPS["finish"]` は `git-worktree-remove` /
    `delete-local-branch`、`worktree_cleanup.FINISH_STEPS` は `verify-pr-merge` …
    `remove-worktree-dir` / `delete-local-branch` であり**別集合**である。
    実 receipt の非空前置列を `reconcile_steps` へ入力すると finish / discard とも
    例外なく `INDETERMINATE` になる。`FLW-REV-015:GP-001` が証明対象とした
    receipt prefix 収束は runtime 私有の閉じた集合内でのみ自明に成立している。
  - **退避と削除の安全境界**（`FLW-REV-016:SYN-010`）:
    `--backup-receipt` は退避の実行も検証も記録も行わない。retention ref は
    commit 済み tip だけを守るため、dirty worktree の discard で未コミット変更が失われる。
    さらに discard の `git branch -D` は retention 済み oid との再照合なしに走り、
    remove → delete の間に進んだ tip が回復不能になりうる。

- **提案する修正**:
  1. step 語彙を単一の SSOT に置き、runtime が書く receipt と cleanup 核が読む step 列を
     同一集合へ統一する。三者照合の機械検査を追加する。
  2. `--backup-receipt` に退避の実行・検証・receipt 記録を実装する。
  3. `git branch -D` の直前に retention 済み oid との一致を再確認する。

- **対象ファイル**: `plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py`、
  `.../worktree_cleanup.py`、`.../recovery.py`、`tests/test_flow_m2_runtime.py`、
  `plugins/bitz-flow/.spec/specs/m2-runtime/test-spec.md`

- **確認観点**:
  - 全 crash 境界で実 receipt の completed 列が cleanup 核の step 列の真の前置になること。
  - dirty worktree の discard で未コミット変更が退避され、退避の成否が receipt に残ること。
  - `branch -D` 直前の再照合により、remove → delete 間で進んだ tip が失われないこと。

- **影響推定・ロールバック**: M3 で受ける破壊系の実装に閉じる。
  receipt 形式が変わる場合は既存 receipt の移行方針を併せて決める。

- **依存**: `SI-FLW-057`（M2 分の例外分類是正）。同じ `apply()` を触るため、
  057 の是正を先に入れてから本件へ進む。予算は後続の予算裁定で確定する。
