---
id: SI-FLW-025
raised_by: M0 測定系の是正（SI-FLW-020 / 021）実施中の発見（2026-08-08）
target: evals/flow-core/m0-eval/run_claude.py / run_antigravity.py の observation と測定不能の扱い
proposed_change_type: modify
status: accepted
---
- **目的**: `SI-FLW-012` / `SI-FLW-014` の裁定で導入した**除外の歯止め**が、
  **codex-cli でしか効いていない**。3 runner は `_task_output` 等の判定ロジックを
  `run_codex.py`（`common`）から共有する一方、**`observation` 辞書と `_one_trial` は
  各 runner が個別に構築している**ため、歯止め用の機構が codex にしか入っていない。
  platform 間で等価でない計装の上で出口条件を判定している点は `SI-FLW-020` と同じ構造である。

- **観測（再実測なし。第10ラウンドの確定記録から）**:

  | 機構 | 導入 | codex | claude | agy |
  |---|---|:-:|:-:|:-:|
  | `measurable`（母数からの除外） | SI-FLW-012 | ○ | **×** | **×** |
  | `harness_retries` による trial やり直し | SI-FLW-012 | ○ | **×** | **×** |
  | `observation.task_output_missing` | SI-FLW-012 | ○ | **×** | **×** |
  | `observation.empty_output_positions` | SI-FLW-012 | ○ | **×** | **×** |
  | `observation.harness_attempts` | SI-FLW-012 | ○ | **×** | **×** |
  | `observation.help_invocations` | SI-FLW-014 | ○ | **×** | **×** |

  ```text
  $ trials-codex-cli-2026-08-07-r10.jsonl   measurable=True
  $ trials-claude-code-2026-08-07-r10.jsonl measurable=False（field 自体が無い）
  $ trials-antigravity-2026-08-07-r10.jsonl measurable=False（同上）
  ```

  `score.py` は `t.get("measurable", True)` で後方互換を取るため、claude / agy の trial は
  **常に「測定できた」として採点される**。すなわち claude / agy には測定不能の概念が無い。

- **これが実害を出した実例**: 2026-08-07 の claude-code 第9ラウンドは、90 trial 中 36 trial が
  Claude のセッション上限（`429 / You've hit your session limit`）で synthetic エラー応答となり
  **v2-skill の 30 trial が全滅**した。エージェントの挙動ではなく上限拒否を測っているにもかかわらず、
  `measurable` を持たないため**素点の FAIL として集計された**。`README.md` にも
  「`SI-FLW-012` で導入した `measurable` フラグは codex の出力欠落専用であり、
  claude のレート制限拒否は対象外である」と記録されている。

- **`SI-FLW-020` との違い**: `SI-FLW-020` は「計装の実体が runner ごとに違う」問題で、
  本件は「**歯止めの機構が runner ごとに有る／無い**」問題である。前者は result code への
  一本化で解いたが、後者は observation の構築そのものが3箇所に散っているため解けていない。

- **提案する修正**:

  1. **`observation` の共通部分を `common` 側の1関数へ寄せる**（推奨）。runner 固有の field
     （`codex_exit_code` / `claude_result_subtype` / `agy_result_status` 等）だけを各 runner が
     足す形にし、歯止め用 field を**構造的に落とせなくする**。
  2. **`measurable` と harness 再試行を3 runner で共通化する**。`_one_trial` の再試行ループを
     `common` へ持ち上げ、各 runner は `_one_attempt` 相当だけを実装する。
  3. **測定不能の検出条件を platform ごとに宣言する**。codex の出力欠落だけでなく、
     claude のレート制限拒否・agy の DONE 未達も「エージェントの判断に起因しない事象」として
     同じ枠で扱えるようにする。条件は runner ごとに違ってよいが、**枠と可視化は共通**にする。
  4. **trial 記録に schema を与える**（`FLW-REV-006` の P1 指摘）。一次証拠である trial 記録に
     schema が無いため、runner 間の構造の差が誰にも検出されないまま10ラウンド続いた。
     必須 field を機械検証すれば本件は初回ラウンドで露見していた。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_codex.py`（`common` 側へ寄せる observation / 再試行）
  - `evals/flow-core/m0-eval/run_claude.py`、`run_antigravity.py`
  - `evals/flow-core/m0-eval/trials.example.jsonl` と新規 trial schema
  - `evals/flow-core/m0-eval/README.md`（測定不能の扱いの節）
  - `tests/test_m0_eval_scoring.py`（3 runner が同じ必須 field を出すことの機械検証）

- **確認観点**:
  - 3 runner の trial 記録が**同一の必須 field 集合**を持つこと（機械検証）
  - claude のレート制限拒否が `measurable: false` として記録され、母数から外れ、
    かつ除外件数が判定出力へ現れること
  - 除外して母数が痩せた場合に `coverage` が「不足」で FAIL すること（歯止めが効くこと）
  - codex の既存挙動（`SI-FLW-012` の検出・再試行）が変わらないこと

- **影響推定・ロールバック**: 変更は harness に閉じ、配布物と v2 fixture に影響しない。
  ただし**3 runner すべてに触れる**ため、`SI-FLW-020` / `SI-FLW-021` とは別 PR とし
  単独 revert 可能に保つ。過去ラウンドの記録は再採点しても `measurable` を持たないため
  結果は変わらない（後方互換の既定は「測定できた」）。

- **依存**: `SI-FLW-012`（`measurable` と harness 再試行の導入。codex 限定であった）。
  `SI-FLW-014`（`help_invocations` の導入。同上）。`SI-FLW-020`（同じ「platform 間で
  等価でない計装」の族。裁定は `.spec/reports/decision-2026-08-08-si-flw-020-021-measurement.md`）。
  `SI-FLW-019`（原因1・原因3 の実例であり、案1・案3 が再発防止に当たる）。
  `FLW-REV-006`（P1「一次証拠である trial 記録に schema が無く、observation の構造が
  3 runner で異なる」）。`FLW-DSN-014`（M0 出口条件）。
