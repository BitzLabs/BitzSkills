---
id: SI-FLW-062
raised_by: SI-FLW-057 実装中に発生した無許可コミット事故（2026-08-15）
target: eval harness が被験エージェントへ与える権限と、被験リポジトリの隔離
proposed_change_type: modify
status: accepted
---

- **目的**: eval harness が起動する被験エージェントから、**被験リポジトリを変更する能力を
  取り上げる**。qualification が測るのは「計測器が観測・分類できるか」であり、
  書き込みは要件上不要である。あわせて hazard / residual を実測して、
  同種の事故を harness 自身が検出できるようにする。

- **発生した事故**（2026-08-15。`FLW-REV-016:SYN-007` が予測した見逃しの実例）:
  - `SI-FLW-057` の作業ツリーで qualification を実行したところ、antigravity の
    **Q-CORRUPT trial が180秒で timeout** した。agy CLI 自体は同条件で5秒応答しており、
    CLI の不調ではない。
  - reflog と commit 時刻が実行区間と一致した。

    ```
    23:41:14 checkout: moving from feat/si-flw-057-… to fix-ci-inspect
    23:41:58 commit  fix(ci): add canonical inspect step to catch broken outputs in workspaces
    23:42:20 antigravity qualification 開始（UTC 14:42:20）
    23:46:19 commit  fix: handle broken outputs in agy_guard and WorktreeRuntimeError
    23:46:28 antigravity qualification 終了（Q-CORRUPT timeout）
    ```

  - **被験エージェントが、観測ではなく修正に走り、ブランチを切って2件コミットした。**
    timeout の原因はその作業である。
  - 改変内容には `scripts/agy_guard.py` の**フェイルオープン化**が含まれていた。
    未一致・パース失敗時の `{}`（無意見＝プラットフォーム既定へ委ねる）を
    `{"decision": "allow"}`（明示的に許可）へ書き換えており、**ガードレールの既定を弱める**。
  - この区間の active manifest は `hazardous_events: 0` / `residual_side_effects: 0` を
    報告し続けていた。固定文字列だったため検出できなかった（`FLW-REV-016:SYN-007`）。

- **原因**:
  - `evals/flow-core/m1-eval/run_qualification.py` の `CLI_COMMANDS`

    | platform | 引数 | 書き込み |
    |---|---|---|
    | antigravity | `--mode accept-edits --sandbox=false --dangerously-skip-permissions` | **無制限** |
    | codex | `--sandbox read-only` | なし |
    | claude | `--setting-sources project --strict-mcp-config`（allowedTools 指定なし） | 設定次第 |

  - `evals/flow-core/m2-eval/run_local_confirmation.py` の codex は
    `--sandbox workspace-write --cd {repo}` であり、こちらも被験リポジトリを書ける。
  - いずれも **`--cd` / cwd が被験リポジトリそのもの**であり、隔離されていない。

- **提案する修正**:
  1. qualification の全 platform を**読み取り専用**で起動する。
     antigravity の `--sandbox=false` と `--dangerously-skip-permissions` を外し、
     claude には allowedTools の閉集合を与える。
  2. confirmation で書き込みが要る場合も、**被験リポジトリではなく使い捨ての複製**を
     cwd にする。実行後に元リポジトリの `git status` / `git worktree list` / ref 一覧を
     比較し、差分があれば hazard として記録する。
  3. hazard / residual を**実測**する（`SI-FLW-058` の `SYN-007` と同一の要求。
     本 issue の事故がその必要性の実例）。
  4. trial が timeout したとき、**副作用の有無を確認してから** BLOCKED を確定する。
     現在は timeout をそのまま BLOCKED にするだけで、残留物を見ていない。

- **対象ファイル**: `evals/flow-core/m1-eval/run_qualification.py`、
  `evals/flow-core/m2-eval/run_local_confirmation.py`、
  `plugins/bitz-flow/.spec/requirements/FLW-NFR-011.md`（隔離要求の明文化）、
  `tests/test_flow_m1_qualification_runner.py`、`tests/test_flow_m2_confirmation.py`

- **確認観点**:
  - qualification 実行後、被験リポジトリの HEAD・ブランチ一覧・作業ツリーが**不変**であること。
  - 意図的に副作用を起こす negative fixture で、hazard が**検出される**こと
    （検出できることを示せない検査は採用しない）。
  - timeout 時に残留副作用の検査が走ること。

- **影響推定・ロールバック**: harness に閉じる。権限を絞ると一部 trial の挙動が変わるため、
  qualification の再校正が要る。被験エージェントが書き込めなくなることで、
  現在 PASS している trial が BLOCKED に変わる可能性がある（それは正しい是正である）。

- **依存**: `SI-FLW-058`（hazard/residual の実測化）と重なる。
  **本 issue が解決するまで harness を再実行しない**方針を採ったため、
  `SI-FLW-057`（PR #282）の confirmation 証跡更新がブロックされている。
