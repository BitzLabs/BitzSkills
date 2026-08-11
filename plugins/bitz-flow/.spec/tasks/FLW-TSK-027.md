---
implements: FLW-NFR-011
depends_on: [FLW-TSK-026]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/coordinator.py, tests/test_flow_m1_coordinator.py
status: done
---

### coordinator core（attempt ID・lease・linearizable CAS・fencing token・authoritative clock）

- **作業内容**: 単一 authoritative coordinator を `flowlib/coordinator.py` として実装する。
  責務を次の5点に限定する。

  - **attempt ID の単調増加採番と 24 時間 lease の発行**。coordinator epoch と attempt counter は
    linearizable CAS で更新し、stale leader による採番と partition 中の offline 採番を禁止する。
  - **fencing token の発行と検査**。各 entry は leader epoch と fencing token を持つ。
    **lease 満了だけでは guard を再発行しない** — owner process 終了・子 Git process 終了・
    OS lock 解放・read-only reconcile を証明し、旧 token を quarantine 確定してから新 token を出す。
    証明できない場合は無期限 `BLOCKED` を安全側の既定とする。
  - **authoritative clock**。時刻の正を coordinator store 側に置き `issued_at` / `completed_at` /
    `expires_at` を発行する。runner の local clock を正にしない。
  - **TTL 検査**。qualification manifest の TTL 24 時間と evidence の TTL 7 日を、
    trial 開始時と mutation（Gate commit）直前の2点で再検査する。実行中・境界時刻での期限切れは
    不適格として `BLOCKED` を返す。
  - **単回 nonce の消費**。`retry_slot_nonce` と authorization capability の nonce を
    `UNUSED → USED_PENDING → USED_DONE / QUARANTINED` で linearizable に遷移させる。
    `USED_PENDING` のまま中断した nonce は reconcile 完了まで再利用不可とする。

  永続化そのものは durable store 側へ委ね、本タスクは採番・CAS・token・時刻の意味論と
  その不変条件に集中する。
- **完了条件**: 上記5責務の単体テストが PASS し、負の対照として次がすべて拒否されること —
  stale leader による採番、lease 満了だけを根拠とする token 再発行、runner clock 由来の時刻、
  境界時刻での TTL 通過、`USED_PENDING` nonce の再利用。
  `.venv/bin/pytest -q` が全件 PASS すること。
- **備考**: coordinator core は qualification と write 安全性の必須基盤であり ROI 判定の対象外
  （FLW-DSN-015 の PR 区分表）。本タスクは Git への副作用を一切持たず、write operation も公開しない。
