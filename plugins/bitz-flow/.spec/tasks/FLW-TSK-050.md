---
implements: FLW-NFR-007, FLW-NFR-011
depends_on: [FLW-TSK-047, FLW-TSK-048, FLW-TSK-049]
boundary: tests/test_flow_m1_ledger_faults.py
status: done
---

### M1-5のfault fixture 13件と統合検証

- **作業内容**: M1-5 の完了条件である fault fixture を
  `tests/test_flow_m1_ledger_faults.py` として実装する。対象は次の 13 件。

  | ID | 注入点 | 期待結果 |
  |---|---|---|
  | `M1-FLT-010` | ledger partition / 未登録 run | runner 未起動、Gate `blocked` |
  | `M1-FLT-011` | FAIL 後に PASS を同 epoch へ登録 | FAIL 置換を拒否 |
  | `M1-FLT-012` | eligibility の事後変更 | 訂正追記、元 entry 保持 |
  | `M1-FLT-013` | model / CLI / event version の変更 | 対象証跡を invalidate |
  | `M1-FLT-014` | raw log の秘密値・期限超過 | qualification / Gate FAIL |
  | `M1-FLT-015` | qualification と confirmation の間の drift | confirmation 未起動 |
  | `M1-FLT-017` | stale coordinator leader が append | fencing 拒否、Gate `blocked` |
  | `M1-FLT-018` | partition 後に late PASS 到着 | `UNKNOWN` 保持、late-evidence は candidate 外 |
  | `M1-FLT-021` | FAIL 後に key / epoch だけ変更 | objective の旧 FAIL 保持、無承認 PASS 置換を拒否 |
  | `M1-FLT-022` | 実行中 / Gate commit 直前の TTL 切れ | candidate 不適格、Gate `blocked` |
  | `M1-FLT-023` | append の temp / rename / fsync 各点 crash | torn entry 隔離、valid chain から RPO 0 復旧 |
  | `M1-FLT-028` | snapshot 直後 / 終了 entry 直後の primary 全損 | replica WAL replay で確認済み entry の欠落 0 |
  | `M1-FLT-030` | retry 不要終了 / retry nonce の二重消費 | 欠番 0、successor 0件または最大1件 |

  fixture ID をテスト名に含め、網羅を機械検査する。

- **完了条件**: `.venv/bin/pytest -q` が全件 PASS し、13 件すべてに対応するテストが存在すること。
  **公開面の非退行**（M1 operation が `UNSUPPORTED` のまま、到達コードが M0 の6件）を確認すること。
  変異試験として、candidate 固定・retry 1回制限・fencing 検査・chain 照合のいずれかを外すと
  対応する fixture が落ちることを確認すること。
  `python3 <リポジトリ>/scripts/release_check.py` が PASS すること。

- **備考**: 本タスクは M1-5 の出口判定である。`M1-FLT-001`〜`009` / `016` / `019` / `020` /
  `024`〜`027` / `029` は M1-3 で検証済みであり、ここには含めない。
