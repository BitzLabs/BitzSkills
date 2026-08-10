---
id: SI-FLW-034
raised_by: 第12ラウンド実測（3 platform。2026-08-10）
target: evals/flow-core/m0-eval/run_claude.py / run_codex.py / run_antigravity.py の platform metadata 既定値
proposed_change_type: modify
status: open
---
- **目的**: run manifest の platform metadata（CLI 版・model version / date）が
  **runner の argparse 既定値のリテラル**であり、実測環境と乖離したまま記録される。
  第12ラウンドは 3 runner すべてで乖離した。

  | runner | manifest に記録された値 | 実測環境の実値（本ラウンド実行前に `--version` で確認） |
  |---|---|---|
  | claude-code | `claude-code 2.1.220` | **`2.1.226`** |
  | codex-cli | `codex-cli 0.146.0` | **`0.147.0`** |
  | antigravity | `agy 1.1.10` | **`1.1.11`** |
  | 3 runner 共通 | `model_version: "2026-08-03 service snapshot"` | 実測日は **2026-08-10**（snapshot 日付は未検証） |

  該当箇所は次のとおりで、いずれも `default=` の固定文字列である。

  ```python
  run_claude.py:435       parser.add_argument("--claude-version", default="claude-code 2.1.220")
  run_codex.py:859        parser.add_argument("--codex-version", default="codex-cli 0.146.0")
  run_antigravity.py:329  parser.add_argument("--agy-version", default="agy 1.1.10")
  ```

- **具体的な害**: 第11ラウンドの manifest は `codex-cli 0.147.0` を記録している
  （実行時に明示指定したため）。第12ラウンドは既定値により `0.146.0` を記録した。
  **記録だけを読むと CLI がラウンド間でダウングレードしたように見える**が、事実ではない。
  ラウンド間の数値比較の前提を保存するという `FLW-REV-006` GP-004 の趣旨
  （`scoring_rule_version` を導入した理由）が、環境側で崩れている。

- **`SI-FLW-027` と同じ形の欠陥である**。同 issue は budget ブロックが定数リテラルで
  一度も更新されなかったことを是正し、「実績値は runner が知り得ないため**既定は `null`**。
  `0` のような事実でない値を書かない」と定めた。
  **CLI 版は runner が知り得る**（`claude --version` 等で機械取得できる）にもかかわらず、
  知り得ない値と同じ扱い＝固定リテラルになっている。`FLW-TSK-012` の固定条件
  「model record: provider、model ID、version / date を run manifest へ記録」は、
  記録される値が真であって初めて満たされる。

- **提案する修正**:
  1. **CLI 版は runner が実行時に取得する**（`<cli> --version` を 1 回呼んで記録）。
     取得に失敗したら `null` を書き、`--*-version` の明示指定でのみ上書きできるようにする。
     **固定リテラルの既定値を廃止する**
  2. **`model_version` の既定を `null` にする**。service snapshot の日付は runner が
     知り得ないため、`SI-FLW-027` の原則どおり明示指定時だけ記録する
  3. `tests/test_m0_eval_runner.py` に、既定値がリテラルでないことの回帰テストを置く
     （`SI-FLW-027` の budget 定数と同じ歯止め）

- **本ラウンドの記録は手で書き換えない**。第12ラウンドの manifest は
  既定値のまま残す。測定記録の手編集は本プロジェクトが一貫して避けてきた行為であり
  （測定系の欠陥はすべて harness の是正と再測定で解消した）、
  **乖離したままの manifest 自体が本 issue の一次証拠**である。
  実値は本 issue と `README.md` の第12ラウンド節に記載する。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_claude.py` / `run_codex.py` / `run_antigravity.py`
  - `evals/flow-core/m0-eval/README.md`（platform metadata の記録規約）
  - `tests/test_m0_eval_runner.py`

- **確認観点**:
  - 3 runner が `--*-version` 未指定でも**実環境の版**を記録すること
  - CLI が取得できない環境で `null` になり、偽の値を書かないこと
  - `model_version` を明示しなければ `null` になること
  - 既定値リテラルを再導入したらテストが落ちること

- **影響推定・ロールバック**: harness に閉じ、配布物・v2 fixture・採点規則
  （`scoring_rule_version`）には影響しない。単独 revert できる。
  過去ラウンドの manifest は遡って修正しない。

- **依存**: `SI-FLW-027`（budget 定数の同型欠陥と「事実でない値を書かない」原則）、
  `FLW-REV-006` GP-004（ラウンド間比較の前提の保存）、`FLW-TSK-012`（model record の固定条件）。
