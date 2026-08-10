---
id: SI-FLW-030
raised_by: 第12ラウンド実測（3 platform。2026-08-10）
target: evals/flow-core/m0-eval/run_antigravity.py の測定不能判定（common.run_trial の measurable 判定）
proposed_change_type: modify
status: open
---
- **目的**: 第12ラウンドの `antigravity / v2-skill / diff-summary #21`（large）が
  **agy CLI の quota 枯渇**で 1 件も command を実行できずに終わったにもかかわらず、
  harness はこれを**測定不能ではなくエージェントの失敗**として集計した。
  raw log の全内容は次の 1 行である。

  ```json
  {"event":"result","result":{"conversation_id":"","status":"ERROR","response":"",
   "error":"Eligibility check failed: RESOURCE_EXHAUSTED (code 429): Resource has been exhausted (e.g. check quota).",
   "duration_seconds":0,"num_turns":0,"usage":{"total_tokens":0}}}
  ```

  記録された trial は `measurable: true` / `harness_attempts: 1` であり、
  **harness 再試行が一度も発動していない**（`--harness-retries` の既定は agy で 2）。
  `duration_seconds: 0` / `command_events: 0` / `usage.total_tokens: 0` であるから、
  **被測定物（v2 SKILL.md と dispatcher）はこの trial で一度も評価されていない**。

- **これは第9ラウンドで claude に起きた事象と同型である**。`README.md` の計装節は
  「claude-code のレート制限拒否（第9ラウンドで v2 30 trial が全滅）が『測定不能』ではなく
  素点の FAIL として集計された」ことを `run_trial()` への一本化で是正したと記している。
  **その一本化は agy の 429 を捕捉していない**。claude は `is_error` / result subtype、
  codex は `aggregated_output` の空を見るのに対し、agy の枯渇は
  `result.status == "ERROR"` かつ `error` に `RESOURCE_EXHAUSTED` を含む形で現れる。

- **影響**: 本ラウンドではこの 1 件が単独で「必須 field 保持 100%」を割り、
  M0 出口の未達 3 点のうち 1 点を構成している（`SI-FLW-033`）。
  すなわち**外部サービスの quota 状態が M0 の合否を決めている**。

- **提案する修正**: agy runner の測定不能判定に、`result.status == "ERROR"` かつ
  `error` が枯渇・レート制限を示す場合（`RESOURCE_EXHAUSTED` / `code 429` /
  `Eligibility check failed`）を加え、`measurable: false` として `run_trial()` の
  harness 再試行へ載せる。再試行を使い切っても測定できなければ trial を
  **測定不能として除外し、その件数を判定出力へ明示する**（黙って母数から落とさない）。
  除外により所要母数を割った場合は `SI-FLW-026` の規則どおり**未達**とする。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_antigravity.py`（測定不能判定）
  - `evals/flow-core/m0-eval/score.py`（測定不能件数の表示。`unmeasurable_v2` は既にある）
  - `evals/flow-core/m0-eval/README.md`（3 runner の測定不能検出の対称性）
  - `tests/test_m0_eval_runner.py`（429 の raw event から `measurable: false` を導く回帰テスト）

- **確認観点**:
  - 上記 raw log を入力として `measurable: false` になり、harness 再試行が発動すること
  - 3 runner の測定不能検出が**同じ事象クラスを覆っている**ことを表で示せること
    （`SI-FLW-025` の「歯止めが codex-cli でしか効いていなかった」の再発防止）
  - 測定不能で除外した trial が judgement 出力に件数として現れること
  - 既存 r12 記録を再採点したとき、この 1 件が失敗から測定不能へ移ること

- **影響推定・ロールバック**: harness に閉じ、配布物（`plugins/bitz-flow/skills/`）と
  v2 fixture には影響しない。単独 revert できる。ただし**過去ラウンドの数値は変わらない**
  （r12 のみ再採点で必須 field 保持が上がる）。

- **依存**: `SI-FLW-012`（測定不能の概念の導入）、`SI-FLW-025`（計装の共通部・runner 間の非対称）、
  `SI-FLW-026`（母数不足は未達）、`SI-FLW-033`（本件が押し下げた指標）。
