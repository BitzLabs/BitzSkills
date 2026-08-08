---
id: SI-FLW-020
raised_by: M0 全10ラウンドの再解析（2026-08-07）
target: evals/flow-core/m0-eval/run_antigravity.py の _commands / run_codex.py の _task_output・self_retried
proposed_change_type: modify
status: accepted
---
- **目的**: harness の `exit_code` は3 runner で**実体が別物**であり、antigravity では
  flow.py の失敗結果を**構造的に検出できない**。この1 field の上に採点規則
  （`_task_output` の成功判定）と `self_retried`（SFCR の減点要因）が乗っているため、
  platform 間で等価でない基準で採点している。

  | runner | `exit_code` の実体 | flow.py の exit 2 を捕捉 |
  |---|---|---|
  | codex-cli | Codex event の `item.exit_code`（実値） | ○ |
  | claude-code | `1 if item["is_error"] else 0`（Bash tool の error flag） | ○ |
  | **antigravity** | 出力に `error` / `failed` / `exit code: 1` を含むかの**文字列判定** | **×** |

  agy runner の該当箇所（`run_antigravity.py` `_commands`）。

  ```python
  # agy の event contract は exit code を独立 field として公開しない。
  # DONE かつ失敗表示が無い実行だけを成功として扱う。
  "exit_code": 1
  if any(marker in output.lower() for marker in ("error", "failed", "exit code: 1"))
  else 0,
  ```

  flow.py は `--base HEAD~1` に対し**実際には exit 2 を返す**（fixture 実測で確認）。

  ```text
  $ flow.py --repo <small> git diff-summary --base HEAD~1
  INVALID_INPUT git.diff-summary cause=invalid-ref stage=inspect
  exit=2  bytes=63
  ```

  この出力に `error` / `failed` / `exit code: 1` は含まれない。よって agy では `exit_code=0` と
  記録される。

- **観測（既存 trial の再解析。再実測していない）**: v2-skill 条件の全ラウンド集計。

  | platform | v2 trial | flow.py 呼出 | **非ゼロ exit の観測** | `self_retried` |
  |---|---:|---:|---:|---:|
  | claude-code | 240 | 226 | 2 | 2 |
  | codex-cli | 312 | 399 | 11 | 11 |
  | **antigravity** | 180 | **242** | **0** | **0** |

  agy は 242 回の flow.py 呼出で**一度も非ゼロ exit を記録していない**。一方、出力 byte 長で
  同定すると diff-summary だけで **38 回 INVALID_INPUT を受けている**（OK は最小 220 B、
  INVALID_INPUT は 63〜64 B で判別可能）。

  | ラウンド | INVALID_INPUT 呼出 | 該当 trial | 採点対象が INVALID になった trial | 非ゼロ exit として記録 |
  |---|---:|---:|---:|---:|
  | r2 | 3 | 3 | 0 | **0** |
  | r3 | 10 | 9 | 0 | **0** |
  | r7 | 10 | 10 | **1** | **0** |
  | r8 | 7 | 7 | 0 | **0** |
  | r10 | 8 | 8 | **2** | **0** |

- **帰結1: `SI-FLW-017` の推奨修正が機能しない**。`SI-FLW-017` の案1は
  「`exit_code == 0` の一致を優先し、成功が無ければ従来どおり最後を採る」であるが、
  **agy では全ての `exit_code` が 0** であるため選択結果は現行と一切変わらない。
  欠陥が観測された当の platform で無効である。`SI-FLW-017` は本 issue へ統合し、
  採点対象の選択は `exit_code` ではなく**出力の result code** で判定する。

- **帰結2: `self_retried` が agy で構造的に永久 false**。判定式は
  `any(item["exit_code"] not in (0, None) for item in relevant) and len(relevant) > 1`
  であり、非ゼロが立たない agy では成立しない。`sfcr()` は `self_retried` を失敗として
  数えるため、**agy の SFCR は過大評価されている**。r7 と r10 は INVALID_INPUT を受けて
  回復した trial を含むが、いずれも自己再試行として計上されていない。

- **帰結3: Cross-model Decision Parity の前提が崩れる**。`FLW-DSN-014` は Parity 100% を
  出口条件に置くが、**platform 間で等価でない計装**の上で判定を比較している。

- **`SI-FLW-017` の記述の訂正**: `SI-FLW-017` は「第10ラウンドで表面化した」「第8Rは
  たまたま失敗呼出が先に来ていた」とするが、再解析では**第7ラウンドでも 1 件発生**しており、
  第8ラウンドは INVALID_INPUT 呼出 7 件があったものの採点対象にはならなかった、が正しい。
  順序依存の露出は r7 / r10 の 2 ラウンドである。

- **提案する修正**:

  1. **result code を出力テキストから読む**（推奨）。compact 出力の先頭トークンは
     `result-v1.schema.json` の `code` enum（`OK` / `READY` / `DONE` / `INVALID_INPUT` /
     `BLOCKED` / `APPROVAL_REQUIRED` / `UNAVAILABLE` / `STALE` / `PARTIAL` / `UNSUPPORTED` /
     `INDETERMINATE`）の 11 値であり、**platform の event contract に依存せず判定できる**。
     `_task_output` の成功判定と `self_retried` の双方をこれに切り替える。
     `--format json` の場合は `code` field を読む
  2. **`exit_code` を trial 記録から削除せず、由来を明示する**。`exit_code_source`
     （`native` / `error-flag` / `heuristic`）を observation へ記録し、
     platform 間で等価でない値を等価であるかのように扱わない
  3. **agy runner のヒューリスティックを撤去する**。1 を入れれば `exit_code` は採点に
     使われなくなるため、誤った 0 を記録し続ける必要が無い。`None`（不明）とする
  4. **採らない案**: marker 文字列に `INVALID_INPUT` 等を足してヒューリスティックを
     強化する。**採らない方向で検討する** — result code の語彙が増えるたびに
     harness 側の文字列一覧が腐り、`SI-FLW-019` が指摘する「実装が事実上の仕様」を
     再生産する

- **除外の歯止め**: `SI-FLW-014` の裁定に倣い、成功 result が1件も無い trial は
  引き続き不合格とする。「成功を優先して選ぶ」ことが「失敗をなかったことにする」に
  ならないようにする。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_codex.py`（`_task_output`・`self_retried`・observation。`common`）
  - `evals/flow-core/m0-eval/run_antigravity.py`（`_commands` の exit_code ヒューリスティック・`self_retried`）
  - `evals/flow-core/m0-eval/run_claude.py`（`self_retried`）
  - `evals/flow-core/m0-eval/README.md`（採点規則の記述）

- **確認観点**:
  - 既存 trial JSONL を**再実測せずに**再採点し、agy の必須 field 保持が r7 / r10 で
    100% へ戻ること
  - agy の `self_retried` が r7 / r10 で**非ゼロになる**こと（過大評価の是正であり、
    数値は下がる方向に動く。下がることを確認する）
  - 全呼出が失敗した trial が引き続き不合格になること
  - claude-code / codex-cli の既達水準を落とさないこと（両者は実 exit code を得ている）
  - `exit_code_source` が3 runner すべてで記録されること

- **影響推定・ロールバック**: 変更は harness に閉じ、配布物と v2 fixture に影響しない。
  単独 revert できる。既存 trial JSONL は再採点で結果が変わるため、どのラウンドを
  どの規則で採点したかを README に明記する。agy の SFCR は**下がる可能性がある**点に注意する
  （過大評価の是正であって退行ではない）。

- **依存**: `SI-FLW-017`（本 issue が統合する。推奨案が機能しないことを示した）。
  `SI-FLW-014`（除外の歯止めの置き方を踏襲する）。`SI-FLW-019`（本 issue は 019 の
  原因1「実装が事実上の仕様」の実例であり、019 の案1・案3 が再発防止に当たる）。
  `SI-FLW-021`（同じ再解析で発見した測定系欠陥）。`FLW-DSN-014`（M0 出口条件）。
