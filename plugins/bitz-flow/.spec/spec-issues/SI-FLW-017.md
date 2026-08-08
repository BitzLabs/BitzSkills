---
id: SI-FLW-017
raised_by: M0 第10ラウンド antigravity 実測（2026-08-07）
target: evals/flow-core/m0-eval/run_codex.py の _task_output
proposed_change_type: modify
status: rejected
---
- **目的**: harness は task の答えとして採点する flow.py 呼出を「一致した呼出のうち**最後の
  もの**」で選ぶ。エージェントが正解を得たあとに探索的な呼出を1回足すと、その**失敗結果**が
  task の答えとして採点され、必須 field 保持が落ちる。エージェントの最終回答は正しいのに
  不合格になる。

  第10ラウンドの実例（`antigravity / v2-skill / diff-summary#1`）。

  ```text
  find . -maxdepth 6 -path '*/flow-core/scripts/flow.py'   ← パス解決（SI-FLW-016）
  flow.py git diff-summary --base HEAD    → OK  227B      ← 正解。この結果で回答している
  flow.py git diff-summary --base HEAD~1  → INVALID_INPUT cause=invalid-ref  64B
  flow.py git status                      → OK  218B
  ```

  最終回答は「6 ファイル / +5 -4 / binary 1 / renamed 1」で oracle と一致する
  （trial の `decision` も `files=6 binary=1 renamed=1 code=OK`）。それでも
  `required_fields_preserved: false` になるのは、`diff-summary` に一致する呼出のうち
  最後が `--base HEAD~1` の `INVALID_INPUT` 行（64B）だからである。

- **原因の所在**: `_task_output`（`run_codex.py`。3 runner が共用）の選択規則。

  ```python
  complete = [item for item in matches if "TRUNCATED " not in item["output"]]
  selected = (complete or matches)[-1]
  ```

  `--help` は `SI-FLW-014` の裁定で除外済みだが、**エラー result は除外されていない**。
  `INVALID_INPUT` / `UNSUPPORTED` は result envelope としては正しい応答であり
  `TRUNCATED` も含まないため `complete` に残り、順番だけで採点対象になる。

- **合否が呼出順で決まっている**: `--base HEAD~1` は agy の v2 `diff-summary`
  10 trial 中 **8 trial**で実行されている。差は「成功呼出の前か後か」だけである。

  | ラウンド | `--base HEAD~1` を実行 | それが最後の一致 | 必須 field 保持 |
  |---|---:|---:|---|
  | 第8R agy | （64B の一致が 6 trial で出現） | **0** | 100% |
  | 第10R agy | 8 | **2** | 93.3% |

  第8ラウンドが 100% だったのは挙動が良かったからではなく、**たまたま失敗呼出が
  成功呼出より先に来ていた**ためである。第10ラウンドの 93.3% も同様に偶然の産物であり、
  どちらの数値も M0 出口判定の根拠として弱い。**これは第10ラウンドで生じた退行ではなく、
  以前から潜在していた採点系の欠陥が表面化したものである**（`SI-FLW-016` の
  fixture 変更とは無関係。同じ順序依存は 3 platform すべてで起こり得る）。

- **これは測定系の取り違えである**: `SI-FLW-012`（出力欠落）・`SI-FLW-014`（`--help`）と
  同じ族であり、`SI-FLW-016` のような正当な失敗ではない。エージェントは終始 flow.py の中に
  留まり（raw fallback 0）、`INVALID_INPUT` を受けて正しく回復し、正しい答えを返している。
  `--base HEAD~1` を試したこと自体は単一コミットの corpus では外れ ref だが、
  dispatcher はそれを契約どおり `cause=invalid-ref` で拒否しており、
  **測っているのは「dispatcher が必須 field を落としたか」であって
  「エージェントが一度も外さなかったか」ではない**。

- **提案する修正**: 次のいずれかを裁定する。

  1. **成功した一致のうち最後のものを選ぶ**（推奨）。`exit_code == 0` の一致を優先し、
     成功が1件も無ければ従来どおり最後の一致を採る。失敗しかしなかった trial は
     引き続き不合格になるため、除外が「なかったこと」にならない
     （`SI-FLW-014` の裁定で置いた歯止めと同じ形）
  2. **エラー result を `--help` と同様に一致から外す**。`INVALID_INPUT` / `UNSUPPORTED` 等の
     判定行で始まる出力を除外する。ただし全呼出が失敗した trial で `matches` が空になり
     `SI-FLW-014` で塞いだ穴が再び開くため、**案1のほうが安全である**
  3. **採点対象を変えず、順序依存を既知の限界として記録するにとどめる**。
     **採らない方向で検討する** — 合否が偶然で決まる状態のまま M0 出口判定を行うことになる

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_codex.py`（`_task_output`。`common` として 3 runner が共用）
  - `evals/flow-core/m0-eval/README.md`（採点規則の記述）

- **確認観点**:
  - 第10ラウンドの trial を**再実測せずに**再採点し、agy の必須 field 保持が
    100% へ戻ること（測定済みデータの解釈だけを変える修正であるため）
  - 全呼出が失敗した trial が引き続き不合格になること（除外の歯止め）
  - `self_retried` の判定を変えないこと（失敗呼出があった事実自体は記録に残す）
  - claude-code / codex-cli の既達水準を落とさないこと

- **影響推定・ロールバック**: 変更は harness の採点関数に閉じ、配布物と v2 fixture に
  影響しない。単独 revert できる。既存 trial JSONL は再採点で結果が変わるため、
  どのラウンドをどの規則で採点したかを README に明記する。

- **依存**: `SI-FLW-014`（`--help` を一致から外した先例。除外の歯止めの置き方を踏襲する）。
  `SI-FLW-012`（測定不能を採点から外した先例）。`FLW-DSN-014`（M0 出口条件）。
