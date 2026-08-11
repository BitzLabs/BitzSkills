---
implements: FLW-NFR-007, FLW-NFR-011
depends_on: [FLW-TSK-026]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/durable.py, tests/test_flow_m1_durable.py
status: done
---

### durable append-only store（原子的置換・hash-chain・torn entry隔離・RPO 0）

- **作業内容**: intent record と evidence ledger が共有する永続化層を `flowlib/durable.py` として実装する。

  - **原子的追記**の順序を temp 作成 → file fsync → atomic rename → directory fsync に固定し、
    **directory fsync 完了を durability commit point** とする。commit point より前に副作用を
    開始できないことを API 契約として表現する（呼び出し順序の誤りを型・状態で弾く）。
  - 書き込み先は対象 repo の Git common-dir 配下の owner-only 領域とする。temp path と秘密本文を公開しない。
  - **hash-chain 追記**。各 entry は `previous_*_digest` で直前 entry を参照し、上書きを構造的に禁止する。
    再 parse と digest 一致検証に成功した場合だけ後続処理へ進む。
  - **起動時の torn entry 隔離**。中断した temp・不完全 entry を隔離し chain の健全性を検査する。
    chain 破損・欠番・重複 ID を検出したら `BLOCKED` を返す（自動修復しない）。
  - **RPO 0 の append**。ack の前に独立 failure domain の同期 replica へ WAL entry と digest を fsync し、
    primary / replica 双方の ack を必須とする。片側が不能なら新しい attempt を開始せず `BLOCKED` にする。
  - 運用 SLI の観測点（append + flush latency、availability、hash-chain / fencing 不整合件数）を
    計測可能な形で公開する。閾値判定そのものは本タスクの責務外。
- **完了条件**: 単体テストが PASS し、crash 注入で不変条件が保たれること —
  temp 作成直後・file fsync 直後・rename 直後・directory fsync 直前の各点で中断しても
  「記録なしの副作用」が 0 件であり、再起動後に torn entry が隔離されること。
  replica ack 欠落時に append が成功扱いにならないこと。
  `.venv/bin/pytest -q` が全件 PASS すること。
- **備考**: FLW-NFR-007 の原子性・完全性要件の実装本体である。
  RPO 0 / RTO 4時間の restore 実証は M1 の evidence 合成区分で行い、本タスクは restore fixture が
  使える形の backup 出力までを用意する。advisory lock・owner-only 永続領域・fsync のいずれかが
  不能な platform では write を `UNSUPPORTED` に落とす判定を返せるようにする。
