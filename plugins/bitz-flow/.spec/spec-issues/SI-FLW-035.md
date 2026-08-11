---
id: SI-FLW-035
raised_by: 第13ラウンド実測（3 platform。2026-08-11）
target: evals/flow-core/m0-eval/run_claude.py の agent_unavailable 判定、run_codex.py の AGENT_UNAVAILABLE_PATTERN
proposed_change_type: modify
status: accepted
github_issue: https://github.com/BitzLabs/BitzSkills/issues/189
---
- **目的**: 第13ラウンドの `claude-code / v2-skill` **63 trial 中 26 trial**が
  Claude Code の**レート制限拒否**で被測定物を一度も評価しなかったにもかかわらず、
  harness はこれを**測定不能ではなくエージェントの失敗**として集計した。
  `SI-FLW-030` の是正（PR #185）で導入した `agent_unavailable` 判定が、
  **claude-code の署名を捕捉できていない**。

  該当 trial の event stream には次が含まれる。

  ```json
  {"type":"rate_limit_event","rate_limit_info":{"status":"rejected",
   "rateLimitType":"five_hour","overageStatus":"rejected",
   "overageDisabledReason":"org_level_disabled","isUsingOverage":false}}
  ```

  ```json
  {"type":"result","subtype":"success","is_error":true,
   "result":"You've hit your session limit · resets 12:40pm (Asia/Tokyo)",
   "num_turns":1,"duration_ms":843,"total_cost_usd":0,
   "usage":{"input_tokens":0,"output_tokens":0}}
  ```

  記録された trial は **`measurable: true` / `agent_unavailable: false` /
  `harness_attempts: 1`** であり、**harness 再試行が一度も発動していない**。
  `command_events: 0` / `tool_events: 0` / `usage.total_tokens: 0` /
  `duration_seconds: 0.3〜0.9` であるから、**被測定物（v2 SKILL.md と dispatcher）は
  この 26 trial で一度も評価されていない**。

- **原因**: 判定に使った proxy が3つとも claude-code の署名から外れている。

  | 判定要素 | 実装 | claude-code での実際 | 乖離 |
  |---|---|---|---|
  | 終了種別 | `result.subtype` を error 文字列へ含める | **`"success"`**（`is_error: true` と矛盾） | 「成功」に見える |
  | 文言一致 | `AGENT_UNAVAILABLE_PATTERN` = `RESOURCE_EXHAUSTED\|quota\|rate[ _-]?limit\|429` | **`"You've hit your session limit"`** | **`session limit` はどの語にも一致しない** |
  | 専用イベント | 参照していない | **`rate_limit_event` の `status: "rejected"`** | **最も確実な信号を読んでいない** |

  すなわち `agy` の署名（`RESOURCE_EXHAUSTED (code 429)` を `error` field に載せる）に
  合わせた proxy を、署名の異なる claude-code へそのまま適用したことが原因である。

- **これは `SI-FLW-019` 原因2 の再発である**。同 issue は「**proxy が measurand から
  乖離する条件を洗い出していない**」を必須案2 として挙げ、PR #185 は危険事象4種について
  乖離条件を `FLW-DSN-014` へ明記した。しかし **`agent_unavailable` 自身の乖離条件は
  platform ごとに列挙していない**。案2 の適用範囲が危険事象に限定され、
  同じ PR で新設した proxy には及んでいなかった。

- **提案する修正**:
  1. **platform 固有の測定不能署名を runner 側で判定する**。共通関数は「実行の痕跡が無いこと」
     の確認に徹し、「測定不能を示す応答か」の判定は各 runner が自 platform の
     event contract で行う（claude は `rate_limit_event.status == "rejected"` と
     `result.is_error`、agy は `error` の `RESOURCE_EXHAUSTED`、codex は stderr）。
  2. **`result.subtype` を成否の判定に使わない**。claude-code は拒否時も `"success"` を返す。
     `is_error` を見る。
  3. **`agent_unavailable` の measurand・proxy・乖離条件を `FLW-DSN-014` の
     「proxy が measurand から乖離する条件」表へ platform ごとに追加する**（案2 の適用範囲の拡張）。
  4. **文言一致は最後の手段とし、単独で使わない**。専用イベント / 構造化フラグがある
     platform ではそれを一次情報にする。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_claude.py`（`_one_attempt` の `claude_error` 組み立て）
  - `evals/flow-core/m0-eval/run_codex.py`（`agent_unavailable` の責務分割）
  - `evals/flow-core/m0-eval/run_antigravity.py`（同じ分割へ追随）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（proxy 乖離条件表）
  - `tests/test_m0_eval_scoring.py`（3 platform 分の署名を回帰で固定する）

- **確認観点**:
  - 第13ラウンドの raw log（`rate_limit_event.status == "rejected"` を含む 26 件）を
    入力にして、**再実測せずに** `agent_unavailable` が立つこと
  - 実行の痕跡がある trial は測定不能にしないこと（`SI-FLW-012` / `SI-FLW-030` の歯止めの維持）
  - 3 runner それぞれの署名について回帰テストがあること。
    **1 platform で直して他へ広げ忘れる**のは `SI-FLW-025` と同型の再発である

- **影響推定・ロールバック**: harness の測定不能判定に閉じる。配布物
  （`plugins/bitz-flow/skills/`）と v2 fixture、被測定物の挙動には影響しない。
  既存 trial 記録は不変だが、第13ラウンドの claude-code 分は
  **本件の是正後に再実測しないと出口判定の証跡にならない**。

- **依存**: `SI-FLW-030`（本件が捕捉し漏らした同一クラスの欠陥）。
  `SI-FLW-019` 案2（proxy の乖離条件。本件はその適用範囲の不足）。
  `SI-FLW-025`（歯止め機構が一部 runner にしか入らない再発パターン）。
  `FLW-DSN-014`（変更対象）。

- **推薦**: accept。構造化イベントを一次情報にする修正は既存のmeasurandを変えず、
  `FLW-NFR-009`のproxy乖離防止をplatform固有署名へ具体化する。公開契約に影響しないため軽量レーン可。

- **実施**: 2026-08-11 `FLW-NFR-010`として要件化し、platform固有拒否署名、実行痕跡の歯止め、
  raw event logの既定永続化を実装・検証した。対応タスクは`FLW-TSK-024`。
