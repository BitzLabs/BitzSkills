---
implements: FLW-NFR-011
depends_on: []
boundary: evals/flow-core/m1-eval/run_qualification.py, tests/test_flow_m1_qualification_runner.py
status: done
---

### 3 platform qualification runner（実CLI起動）

- **作業内容**: `evals/flow-core/m1-eval/run_qualification.py` に、3 platform の**実 CLI を起動**して
  qualification の 3 trial を実行する runner を実装する。

  - platform（`claude` / `codex` / `antigravity`）ごとに CLI を起動し、
    `Q-NORMAL` / `Q-REJECT` / `Q-CORRUPT` を**各ちょうど1件**実行する。
  - trial の観測結果を `qualification.TrialOutcome` へ落とし、Gate 判定は既存の
    `qualification.evaluate` に委ねる（判定ロジックをここで再実装しない）。
  - **read-only の operation だけを被験対象にする**。M1 operation は未公開であり、
    本区分は計測器の適格化に限る（裁定: `.spec/reports/decision-2026-08-12-m1-6-scope.md`）。
  - 隔離 namespace（`isolation.py`）・raw log guard（`raw_log_guard.py`）・
    coordinator の lease / TTL を実際に通す。
  - CLI が見つからない platform は **`blocked`** として記録し、「実行できなかった」ことを
    「合格」と読み替えない。
  - 実行時間・harness 再試行回数を計測し、10分・1回の制約判定へ渡す。
  - `--dry-run` で CLI を起動せず配線だけを検査できるようにする（CI ではこちらを使う）。
  - CLI 契約（`CORE-CON-011`）に従い argparse を使い、未知引数で非ゼロ終了する。

- **完了条件**: `--dry-run` の単体テストが PASS し、次が確認できること —
  3 platform × 3 trial の組が過不足なく構成されること、CLI 不在の platform が `blocked` に
  なること（合格にしない）、Gate 判定を `qualification.evaluate` に委ねていること、
  raw log が owner-only で canary 検出済みであること、隔離 namespace が trial ごとに独立すること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: 実 CLI の起動は課金と時間を伴うため、**CI では `--dry-run` のみ**を回す。
  実走は次のタスクで人手により1回行い、結果を成果物として記録する。
