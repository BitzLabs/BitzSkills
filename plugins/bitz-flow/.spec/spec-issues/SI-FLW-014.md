---
id: SI-FLW-014
raised_by: M0 第7ラウンド antigravity 実測（2026-08-06）
target: M0 eval harness の TASK_FLOW_PATTERN と _task_output（採点対象の選び方）
proposed_change_type: modify
status: open
---
- **目的**: `flow.py <domain> <action> --help` の実行が **task の実行として拾われ**、
  その usage テキストが採点対象になる。エージェントは正しい実行を済ませたうえで
  ヘルプを見ているにもかかわらず、必須 field 保持が `false` になる。

  第7ラウンドの `v2-skill/dirty-status#1` の実例。

  ```text
   218B  flow.py git status          ← 正しい実行。必須 field はここに揃っている
  1238B  flow.py git status --help   ← これが採点対象になった
  ```

  原因は照合パターンと選択規則の組み合わせである。

  ```python
  TASK_FLOW_PATTERN = {
      "dirty-status": re.compile(r"\bflow\.py\b.*\bgit\s+status\b", re.DOTALL),
      ...
  }
  # _task_output: complete な match の **最後** を採点対象にする
  selected = (complete or matches)[-1]
  ```

  `flow.py git status --help` は `flow\.py.*git\s+status` に一致するため task の実行と
  見なされ、最後の実行であるため採点値になる。

- **`--help` は operation の実行ではない**: `--help` が返すのは argparse の usage であり、
  result envelope ではない。

  ```text
  usage: flow.py [-h] [--repo REPO] [--format {compact,json}]
                 [--timeout-seconds TIMEOUT_SECONDS] [--base BASE]
                 ...
  ```

  `code` も `operation` も `snapshot` も無いため、必須 field の検査は必ず落ちる。
  すなわちこれは**エージェントの失敗ではなく採点系の取り違え**であり、
  `SI-FLW-012`（出力欠落を失敗と誤読していた件）と同種である。

- **影響範囲**: 第7ラウンドで `--help` を実行したのは antigravity だけである。

  | platform | v2 trial 数 | `--help` を実行した trial |
  |---|---:|---:|
  | claude-code（第6R） | 30 | **0** |
  | codex-cli（第6R） | 30 | **0** |
  | antigravity（第7R） | 30 | **2** |

  影響したのは `dirty-status#1` の 1 trial（必須 field 保持 93.3% の 2 件のうち 1 件）。
  もう 1 件（`diff-summary#7`）は `--base HEAD~1` という**比較元の誤り**であり、
  本 issue の対象ではない**正当な失敗**である（prompt は「直前のコミットからの変更量」を問うため
  `--base HEAD` が正解。実測でも結果はほぼ空の 64 B）。

- **提案する修正**: `--help` / `-h` を伴う実行を task の実行から除外する。

  1. **除外を照合側で行う**（推奨）。`_task_output` が match を集める際に、
     `--help` / `-h` を含む実行を落とす。`TASK_FLOW_PATTERN` 自体は変えない
     （否定先読みでパターンを複雑にするより、選択規則で落とすほうが読みやすい）
  2. `first_git_action` の判定からも `--help` を除くかは**別問題**として扱う。
     `--help` であっても「生 git ではなく `flow.py` を選んだ」ことは事実であり、
     入口遵守の観点では成功として数えてよい。本 issue では変更しない

  併せて、除外した実行があったことを trial 記録へ残す
  （`observation.help_invocations` 等）。`SI-FLW-010` / `SI-FLW-012` と同じく
  **判定根拠を分けて残す**方針を踏襲し、黙って捨てない。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_codex.py`（`_task_output`。3 runner が共用する）

- **確認観点**:
  - `--help` を実行した trial で、その直前の正しい実行が採点対象になること
  - `--help` **しか**実行しなかった trial は、task を実行していないため
    従来どおり失敗として扱われること（除外が「なかったこと」にならない）
  - `--base HEAD~1` のような**比較元の誤り**は引き続き失敗として数えること
    （本 issue の除外規則がエージェントの誤りを覆い隠さない）
  - claude-code / codex-cli の既存結果が変わらないこと（両者は `--help` 0 件のため不変のはず）

- **影響推定・ロールバック**: 変更対象は `evals/` 配下の測定系のみで、配布物
  （`plugins/bitz-flow/`）には触れない。ロールバック単位は本 issue に対応する PR 1件。

- **依存**: `SI-FLW-012`（測定系の欠陥を被測定物の欠陥と取り違えない方針。判定根拠を
  分けて残す方針を踏襲する）。`SI-FLW-013`（同じ第7ラウンドで検証した SKILL.md 修正。
  独立に扱える）。
