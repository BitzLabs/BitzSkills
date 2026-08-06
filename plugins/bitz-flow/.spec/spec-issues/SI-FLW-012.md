---
id: SI-FLW-012
raised_by: M0 第3ラウンド codex-cli 実測（2026-08-06）
target: M0 eval harness（run_codex.py）の command_execution 出力キャプチャ
proposed_change_type: modify
status: open
---
- **目的**: codex-cli の trial で、`flow.py` が `exit_code: 0` を返しているにもかかわらず
  `aggregated_output` が**空文字列**になる事象がある。同じコマンドを直接実行すれば
  120 byte を出力するため、**flow.py 側の欠陥ではない**。

  ```json
  {"type": "item.completed", "item": {"id": "item_2", "type": "command_execution",
   "command": "/bin/bash -lc 'python3 .agents/skills/flow-core/scripts/flow.py ... repo inspect'",
   "aggregated_output": "", "exit_code": 0, "status": "completed"}}
  ```

  発生条件は決定的である。第3ラウンドの全 raw log を集計した結果、

  | 観測 | 値 |
  |---|---|
  | `flow.py` の実行総数 | 99 |
  | 出力0かつ exit 0 | **15**（15.2%） |
  | 発生位置（セッション内の何番目の `command_execution` か） | **100% が2番目** |

  すなわち **セッション内で最初の `flow.py` 呼び出し**（1番目は SKILL.md を読む `sed`）でのみ
  起きる。毎回ではなく、90 セッション中 15 セッションで発生する。

- **採点への影響**: task 別に影響が異なる。`repo-inspect` は最初の `flow.py` 呼び出しが
  そのまま task 対象になるため直撃し、**v2 の 4 trial が `reached_expected_state=false` かつ
  `required_fields_preserved=false`** となった。`dirty-status` / `diff-summary` では最初の
  呼び出しが探索目的で、task 対象の呼び出しは後続のため影響しない。

  結果として codex-cli の必須 field 保持は **86.7%**（閾値 100%）となった。ただし
  **本欠陥を除いても SFCR は 61.5% で閾値未達**であり（残る失敗は `SI-FLW-011` に起因）、
  本 issue だけで第3ラウンドの結論が覆るわけではない。

- **第1ラウンドとの関係**: 第1ラウンドで「codex `v2-skill/repo-inspect` の 9/10 が
  exit 0 なのに出力 0 byte」を観測し、当時は raw log が無いため切り分け不能だった。
  第2ラウンドでは 10/10 が 120 byte となり**解消したと判断した**が、本ラウンドで再発した。
  したがって「第2ラウンドで解消」は誤りであり、**確率的に発生する事象をたまたま観測しなかった**
  というのが正しい理解である。この誤判定を記録として残す。

- **提案する修正**: 原因の切り分けから行う。少なくとも次を区別する必要がある。

  1. **codex 側の event stream の問題** — `item.completed` の `aggregated_output` が
     ストリーミング競合で欠落する。harness は `item.completed` だけでなく
     途中の delta event も蓄積して突き合わせる必要がある。
  2. **harness の parse の問題** — `_events()` / `_commands()` が特定の event 順序で
     出力を取りこぼす。
  3. **実行環境の問題** — `--sandbox read-only` 下での初回 python 実行時の
     stdout バッファリング。

  切り分けの手順として、`--keep-logs` の raw JSONL に対し `item.completed` 以外の
  event 種別（delta / output chunk）を保存する harness 変更を先に入れ、再実測で
  「codex が出していないのか、harness が捨てているのか」を確定させる。

  併せて、**出力0かつ exit 0 を trial 記録上で明示する**。現状は
  `task_flow_output_bytes: [0]` として記録されるだけで、正常な空結果と区別できない。
  `observation.empty_output_positions` のような field を足し、採点時に
  「測定不能」として除外できるようにする（`SI-FLW-010` で `state_change_reasons` を
  足したのと同じ方針＝判定根拠を分けて残す）。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_codex.py`（`_events` / `_commands` / raw log 保存）
  - `evals/flow-core/m0-eval/score.py`（測定不能 trial の扱い）
  - `evals/flow-core/m0-eval/README.md`（現況と既知欠陥）

- **確認観点**:
  - 再実測で出力0かつ exit 0 の発生率が下がること。下がらない場合は codex 側の挙動として
    確定し、trial を「測定不能」として除外する規則を裁定すること
  - 除外規則を入れる場合、**数値を通すための都合のよい除外にならない**こと。除外は
    「エージェントの判断に起因しない事象」に限り、raw log で裏取りできる場合のみとする
  - `repo-inspect` 以外の task でも同じ欠落が起きていないかを機械的に検査すること

- **影響推定・ロールバック**: 変更対象は `evals/` 配下の測定系のみで、配布物
  （`plugins/bitz-flow/`）には触れない。ロールバック単位は本 issue に対応する PR 1件。

- **依存**: `SI-FLW-010`（同じく harness 欠陥の裁定。判定根拠を分けて残す方針を踏襲する）。
  `SI-FLW-011` とは独立に修正できる。

- **第4ラウンドでの再現（2026-08-06 追記）**: `SI-FLW-011` の修正後に同条件で再実測したところ、
  本欠陥は再現した。発生率は振れるが**発生位置は変わらない**。

  | ラウンド | flow.py 実行回数 | 出力0かつ exit0 | 発生率 | 発生位置 |
  |---|---:|---:|---:|---|
  | 第3R | 99 | 15 | 15.2% | 100% が2番目 |
  | 第4R | 81 | 21 | 25.9% | 100% が2番目 |

  発生率が2ラウンドで倍近く振れることは、「確率的に発生する事象」という読みを補強する。

  第4ラウンドでは `SI-FLW-011` 起因の失敗が 0 件になったため、**codex-cli の未達は本 issue が
  単独の原因**になった。v2 30 trial 中 7 trial が該当し、SFCR 76.7% / 必須 field 保持 76.7% の
  未達はすべてこれで説明できる。**当該 7 trial を除くと 23/23 = 100%** である。
  したがって本 issue の解消なしに codex-cli は M0 出口条件を満たせない。
