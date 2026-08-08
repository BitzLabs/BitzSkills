---
id: SI-FLW-027
raised_by: 第11ラウンド準備時の runner 再監査（2026-08-08）
target: evals/flow-core/m0-eval/run_*.py の run manifest budget ブロックと FLW-DSN-014 の予算記録手順
proposed_change_type: modify
status: accepted
---
- **目的**: `FLW-DSN-014` は「各milestone開始時に、**実績PR数、実績session数、レビュー修正回数、
  出口未達理由を run manifest へ記録し**、人間が次budgetの維持または変更を確認する」と定めている。
  run manifest には**そのための field が最初から存在した**にもかかわらず、
  **3 runner とも定数リテラルで書いており、全10ラウンドで一度も更新されなかった**。
  `FLW-REV-006` SYN-003 / GP-001 が「安全弁が一度も発動しなかった」とした事象の、
  **機械的な理由**がこれである。

- **観測（第10ラウンドの確定記録。3 platform すべて同一）**:

  ```json
  "budget": {
    "max_prs": 1,          // 設計当初の値。GP-001 で 3 へ再校正済み
    "max_sessions": 5,     // 同上。10 へ再校正済み
    "actual_prs": 0,       // 実績は #158 以降で 17。0 は事実でない
    "actual_sessions": 1,  // 同上
    "review_fix_rounds": 0,
    "exit_miss_reasons": [],
    "budget_reconfirmation_ref": null   // 再確認は一度も行われていない
  }
  ```

  `actual_prs: 0` は 17 PR を消費した時点でも `0` のままであり、
  `budget_reconfirmation_ref: null` は「再確認が必要な状態に達していない」ようにしか読めない。
  **予算超過を run manifest から見る手順は、記録先が定数だったため実質的に動いていなかった。**

- **これは `SI-FLW-025` と同じ族である**: 裁定で置いた手順（`FLW-DSN-014` の予算再確認）が、
  実装側では**到達不能な形**で置かれていた。`SI-FLW-025` は歯止め用 field が
  1 runner にしか無かった問題、本件は記録先が**定数だった**問題で、
  どちらも「仕組みはあるが働いていない」ことが**データ構造上検出できなかった**。

- **`0` を既定値にしたことが害を大きくした**: 実績値は runner が知り得ない。
  それを `0` と書くと「測ったが 0 だった」と読め、`null`（未記入）と区別できない。
  `SI-FLW-025` で見た「記録されていない」と「記録されたが偽」の混同と同型である。

- **提案する修正**:

  1. **予算を定数リテラルから共有定数へ移し、GP-001 の再校正値と裁定記録の参照を持たせる**（推奨）。
     `M0_BUDGET`（`run_codex.py` = common）に `max_prs` / `max_sessions` /
     `consumed_prs_before_recalibration` / `budget_reconfirmation_ref` を置き、3 runner が読む。
  2. **実績値の既定を `null` にする**。`--actual-prs` / `--actual-sessions` /
     `--review-fix-rounds` で明示的に与えたときだけ値を書く。**`0` のような事実でない
     既定値を書かない**。
  3. **予算値と裁定記録の存在をテストで固定する**。`budget_reconfirmation_ref` が
     実在するファイルを指すこと、再校正値が `FLW-DSN-014` と一致することを機械検証する。
  4. **予算消費の自動集計は本 issue では行わない**。`actual_prs` を runner が git 履歴から
     数えるのは責務違反であり、bitz-sdd テーマ13-E（マイルストーン予算の成果物化）の
     裁定を待つ。本 issue は「事実でない値を書かない」ところまでとする。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_codex.py`（`M0_BUDGET` の定義と CLI）
  - `evals/flow-core/m0-eval/run_claude.py`、`run_antigravity.py`
  - `tests/test_m0_eval_runner.py`（新規。runner の CLI・job 構築・manifest の契約テスト）

- **確認観点**:
  - 3 runner の manifest が同じ再校正値（`max_prs: 3` / `max_sessions: 10`）を書くこと
  - `budget_reconfirmation_ref` が実在する裁定記録を指すこと
  - `--actual-prs` 等を与えないとき `null` が書かれること（`0` でないこと）
  - 予算を旧値へ戻す変更をテストが検出すること（負の対照）

- **影響推定・ロールバック**: 変更は harness に閉じ、配布物と v2 fixture に影響しない。
  単独 revert できる。過去ラウンドの manifest は書き換えない（当時の記録として残す）。

- **依存**: `FLW-REV-006`（SYN-003 / GP-001。安全弁が発動しなかった事象）。
  `SI-FLW-025`（同族。「仕組みはあるが働いていない」がデータ構造上検出できない）。
  `FLW-DSN-014`（予算記録の手順と、GP-001 で再校正した値）。
  bitz-sdd ROADMAP テーマ13-E（マイルストーン予算の成果物化。自動集計はそちらの裁定待ち）。
  裁定は `.spec/reports/decision-2026-08-08-round11-harness-readiness.md`。
