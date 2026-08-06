---
implements: FLW-NFR-001
depends_on: FLW-TSK-012
boundary: evals/flow-core/m0-eval/run_codex.py, evals/flow-core/m0-eval/score.py, evals/flow-core/m0-eval/README.md
status: done
---

### SI-FLW-012 の裁定に基づき測定不能な trial を harness 側で再実行する

- **作業内容**: `SI-FLW-012` の裁定（accept・案1）に基づき、出力欠落を**失敗ではなく測定不能**
  として扱い、harness 側で trial をやり直す。

  | 変更 | 内容 |
  |---|---|
  | 検出 | `_empty_output_positions()` が「出力0かつ exit 0 の `flow.py` 実行」の位置を返す |
  | 再試行 | `_one_trial()` が測定不能を検出したら `--harness-retries`（既定2）まで trial ごとやり直す |
  | 記録 | `observation.empty_output_positions` と `observation.harness_attempts`、trial 直下に `measurable` |
  | 採点 | `_cell()` が `measurable: false` を母数から外す。`coverage` も**測定可能な件数で**数える |
  | 可視化 | 判定出力の platform 行へ `測定不能=N（raw log で裏取りすること）` を表示する |

  再試行は**エージェントの自己再試行とは別物**であり `self_retried` には計上しない
  （`self_retried` はエージェントの判断の質を測る指標であり、測定系の都合で汚さない）。

- **完了条件**:
  1. 実機で再試行が機能すること（測定不能を検出した trial がやり直しで `measurable: true` になる）
  2. 除外が**黙って行われない**こと（判定出力に件数が出る）
  3. 除外で母数が痩せたら `coverage` が「不足」として捕捉すること
  4. `measurable` を持たない旧 trial 記録が従来どおり採点されること（後方互換）

- **検証結果**:
  - 実機 2 trial のパイロットで、1 件が `harness_attempts: 2` を経て `measurable: true` /
    `reached: true` / `fields: true` となった。従来なら失敗と採点されていた trial である
  - 合成データ（第4ラウンドの 7 件へ `measurable: false` を付与）で
    `trials=23 測定不能=7（raw log で裏取りすること）` と表示され、
    `codex-cli/v2-skill/repo-inspect: 3/10 trial（不足）` が同時に立つことを確認した
  - 第3・第4ラウンドの既存 trial（`measurable` なし）は従来どおりの採点結果になることを確認した

- **備考**: 除外規則が**数値を通すための都合のよい除外**にならないよう、次の2点で歯止めをかけた。
  (1) 除外しても `coverage` が所要件数を測定可能な件数で判定するため、除外して母数が痩せれば
  必ず「不足」で FAIL する。(2) runner の異常終了（`runner_error`）は `measurable: true` のままとし、
  runner のバグを測定不能の隠れ蓑にしない。
  裁定記録は `.spec/reports/decision-2026-08-06-si-flw-012-empty-output.md`。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
