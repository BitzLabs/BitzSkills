---
implements: FLW-NFR-007, FLW-NFR-011
depends_on: [FLW-TSK-048]
boundary: evals/flow-core/m1-eval/recovery_ops.py, tests/test_flow_m1_recovery_ops.py
status: pending
---

### 台帳のbackup / restore（RPO 0・RTO 4時間）

- **作業内容**: `evals/flow-core/m1-eval/recovery_ops.py` に正本台帳の保全と復旧を実装する。

  - **confirmation 前に正本 snapshot を暗号化 backup** する。
  - **restore fixture** を用意し、primary 全損から **RPO 0**（確認済み entry の欠落 0）で
    復旧できることを検証する。replica の WAL replay で chain が再構成できること。
  - **RTO 4時間**の運用手順を、時間を計測できる形で記述する（手順の所要時間を記録する）。
  - 復旧後の台帳が**元と同じ digest chain** を持つこと、`UNKNOWN` の扱いが変わらないことを確認する。
  - 運用 SLI（coordinator availability・append+flush latency p95・hash-chain 不整合件数）の
    閾値超過を検出できる形で公開する。判定そのものは呼出側。

- **完了条件**: 単体テストが PASS し、次が確認できること —
  backup が暗号化されていること（平文で秘密値が残らない）、primary 全損後に replica WAL から
  復旧して**確認済み entry の欠落が 0** であること、復旧後の chain digest が一致すること、
  restore の所要時間が記録されること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: `FLW-DSN-015` は「M1 中に最低1回 restore fixture で RPO/RTO を検証する」と定めており、
  本タスクがその1回にあたる。
