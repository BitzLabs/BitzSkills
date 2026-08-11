---
implements: FLW-NFR-011
depends_on: [FLW-TSK-033, FLW-TSK-034, FLW-TSK-035]
boundary: evals/flow-core/m1-eval/fixtures/, tests/test_flow_m1_qualification_fixture.py
status: pending
---

### 3 platform qualification fixtureと統合fault

- **作業内容**: M1-2 の出口条件「M1-1 core を使用して全 platform qualification fixture PASS」を
  満たす fixture と統合 fault を作る。

  - `evals/flow-core/m1-eval/fixtures/` に **3 platform（claude / codex / antigravity）分の
    qualification fixture** を置く。各 platform の adapter が返す observation を模した固定入力とし、
    実 CLI を起動しない（実接続は M1-6 confirmation）。
  - fixture を使って **3 platform すべてで qualification が PASS する**ことを検証する。
    PASS した manifest を成果物として保存し、以後の回帰判定の基準にする。
  - **統合 fault**（モジュールをまたぐもの）を検証する。
    - qualification が FAIL / BLOCKED のとき confirmation が起動しないこと
    - lease 期限切れ・lease 切替後の trial が `BLOCKED` になること
    - raw log の canary 未検出で Gate が止まること
    - 残存副作用がある fixture で PASS しないこと
    - 1 platform だけ FAIL のとき全体が PASS にならないこと（平均で相殺しない）
  - **変異試験**: 合格条件を1つ緩める（denominator 0 を許す・positive-control 0 を許す・
    hazardous event 1 件を許す・trial 件数チェックを外す）と、対応する検査が落ちることを確認する。

- **完了条件**: `.venv/bin/pytest -q` が全件 PASS すること。
  3 platform 分の fixture で qualification が PASS し、manifest が
  qualification manifest schema の必須 field をすべて満たすこと。
  上記4種の変異で対応するテストが確実に落ちること。
  `python3 <リポジトリ>/scripts/release_check.py` が PASS すること。

- **備考**: 本タスクは M1-2 の出口判定そのものであり、ここが PASS しない限り M1-3 以降へ進まない
  （M1-2 は M1 最初の blocking Go/No-Go）。実 platform CLI での qualification 実走は
  M1-6 confirmation で行う。
