---
implements: FLW-FR-013, FLW-NFR-007, FLW-NFR-011, FLW-NFR-012
depends_on: [FLW-TSK-027, FLW-TSK-028, FLW-TSK-029, FLW-TSK-030]
boundary: tests/test_flow_m1_core.py, tests/fixtures/flow/m1/
status: pending
---

### M1-1 coreのfault testと負の対照（変異試験）

- **作業内容**: M1-1 の完了条件「core の単体 fault test、契約表と負の対照 PASS」を
  `tests/test_flow_m1_core.py` として実装する。検証対象は次のとおり。

  - **契約表との一致**: 凍結した5つの enum namespace の値集合、intent record v1 schema、
    evidence ledger entry schema、guard identity の閉集合が `schemas/` と `references/` の双方で
    同一であること（片方だけの変更を検出できること）。
  - **recovery matrix の全行**: 決定器の出力が表と一致し、未登録 tuple が `human-stop` へ
    fail-closed すること。到達不能 tuple が構築されないこと。
  - **crash 注入**: durable store の temp 作成直後 / file fsync 直後 / rename 直後 /
    directory fsync 直前で中断し、「記録なしの副作用」が 0 件であること、再起動後に torn entry が
    隔離されること。replica ack 欠落時に append が成功扱いにならないこと。
  - **coordinator の負の対照**: stale leader 採番、lease 満了だけを根拠とする token 再発行、
    runner clock 由来の時刻、境界時刻での TTL 通過、`USED_PENDING` nonce の再利用が拒否されること。
  - **sanitizer の負の対照**: 秘密値 canary の検出率 100%、誤検出 0。
  - **公開面の非退行**: 公開 operation 集合が M0 から増えていないこと、write 系引数
    （`--apply` / `--confirm` / `--approval-ref`）が引き続き副作用なしで `UNSUPPORTED` を返すこと、
    到達する終了コードが M0 の6件のままであること。

  fixture は `tests/fixtures/flow/m1/` に置き、既存 `tests/conftest.py` の共有 fixture と
  `tests/test_flow_contract.py` の規約に合わせる。
- **完了条件**: `.venv/bin/pytest -q` が全件 PASS すること。
  **変異試験**として、recovery matrix の1行を削る・enum 値を1つ増やす・durable の directory fsync を
  省く・sanitizer の遮断を1つ外す、の各改変で対応するテストが確実に落ちること。
  `python3 <リポジトリ>/scripts/release_check.py` が PASS すること。
- **備考**: 本タスクは M1-1 の出口判定そのものであり、ここが PASS しない限り M1-2 qualification へ進まない。
  write operation の実測（3 trial・隔離 namespace）は M1-2 以降で行い、本タスクには含めない。
  各モジュールの単体テストは実装タスク側（coordinator / durable / recovery / sanitize）が持つ。
  本タスクが持つのは**モジュールをまたぐ統合 fault、契約表と schema の相互照合、変異試験**であり、
  単体テストの再実装ではない。
