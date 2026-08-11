---
implements: FLW-FR-004, FLW-FR-005, FLW-FR-011, FLW-NFR-003
depends_on: [FLW-TSK-042, FLW-TSK-043, FLW-TSK-044, FLW-TSK-045]
boundary: tests/test_flow_m1_contract_rows.py
status: done
---

### M1 operation contract全行の検証

- **作業内容**: M1-4 の完了条件「M1 contract 全行 PASS」を
  `tests/test_flow_m1_contract_rows.py` として実装する。

  - `references/operation-catalog.md` の M1 節に書いた **12 operation の contract 全行**について、
    `class` / `approval` / `retry` / `concurrency_key` と、
    `target` / `preconditions` / `effects` / `postconditions` / `partial` / `recovery` / `evidence` が
    実装の振る舞いと一致することを検証する。
  - **catalog と実装の突合**を機械的に行い、片方だけの変更を検出できるようにする。
  - **公開面の非退行**: 12 operation すべてが引き続き `UNSUPPORTED`（effects 空）で、
    到達コードが M0 の 6 件のままであること、dispatcher の handler 表が 3 operation のままであること。
  - **禁止事項の非提示**: `reset` / `clean` / force push / rebase / stash / passthrough / `git config` が
    実装にも診断にも next action にも現れないこと。
  - **重複 commit 0**: 同じ plan から二重に commit object や ref 更新が生じないこと。

- **完了条件**: `.venv/bin/pytest -q` が全件 PASS し、catalog の M1 operation 全行が
  検証対象に含まれていること（網羅を機械検査する）。
  変異試験として、catalog の `class` を1つ書き換えると突合が落ちること。
  `python3 <リポジトリ>/scripts/release_check.py` が PASS すること。

- **備考**: 本タスクは M1-4 の出口判定そのものである。実 platform CLI・実 GitHub での確認は
  M1-6 confirmation が扱う。
