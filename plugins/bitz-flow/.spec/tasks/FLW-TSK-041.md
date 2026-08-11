---
implements: FLW-NFR-003, FLW-NFR-007, FLW-NFR-012, FLW-FR-013
depends_on: [FLW-TSK-037, FLW-TSK-038, FLW-TSK-039, FLW-TSK-040]
boundary: tests/test_flow_m1_write_faults.py
status: done
---

### M1-3のfault fixture 17件と統合検証

- **作業内容**: M1-3 の完了条件である fault fixture を
  `tests/test_flow_m1_write_faults.py` として実装する。対象は次の 17 件。

  | ID | 注入点 | 期待結果 |
  |---|---|---|
  | `M1-FLT-001` | intent の temp / file-fsync / rename / directory-fsync 各点 crash | record 不在なら副作用 0 証明後 replan、完全 pending なら BLOCKED、不完全 / torn なら quarantine |
  | `M1-FLT-002` | intent fsync 後・mutation 前 crash | pending 保持、次回 write BLOCKED |
  | `M1-FLT-003` | commit CAS 直後 crash | receipt 欠落なら INDETERMINATE、quarantine 保持 |
  | `M1-FLT-004` | reconcile 中 crash | pending 保持、blind retry 0 |
  | `M1-FLT-005` | stage / commit の cross-family 競合 | 同時 mutation 最大 1、敗者の副作用 0 |
  | `M1-FLT-006` | 複数 target の逆順要求 | canonical 順へ正規化、または副作用 0 で拒否 |
  | `M1-FLT-007` | 副作用後の output-limit | reconcile で収束、command 再実行 0 |
  | `M1-FLT-008` | 未知の recovery tuple | 空 NEXT ＋ human-stop |
  | `M1-FLT-009` | NEXT chain に apply を混入 | graph 検査で FAIL |
  | `M1-FLT-016` | pre-object intent 直後 / object 保存直後 crash | ref 不変、no-effect または quarantine へ一意化 |
  | `M1-FLT-019` | symlink / case / worktree alias で同一 target 要求 | 同一 guard へ収束、同時 mutation 0 か 1 |
  | `M1-FLT-020` | authorization nonce の再利用・別 target 転用 | mutation 前に拒否 |
  | `M1-FLT-024` | 別 clone・worktree・remote alias から同一 remote ref 要求 | 同一 remote guard へ収束、同時 publish 最大 1 |
  | `M1-FLT-025` | token 照合後 pause → lease 満了 → guard 再発行要求 | 旧 owner / child / lock の停止証明までは再発行拒否 |
  | `M1-FLT-026` | object 保存後・CAS 前 crash | orphan-object 結論、object 保持のまま承認解除 |
  | `M1-FLT-027` | capability nonce 消費の各点 crash・key 失効 | replay 拒否、`USED_PENDING` は quarantine |
  | `M1-FLT-029` | index digest 照合直後に外部 `git add` が割込み | native `index.lock` で排他、無視する writer は quarantine |

  fixture ID をテスト名に含め、どの fixture がどのテストに対応するか機械的に辿れるようにする。

- **完了条件**: `.venv/bin/pytest -q` が全件 PASS し、上記 17 件すべてに対応するテストが存在すること。
  **公開面の非退行**として、`git.stage` / `git.commit` が引き続き副作用なしで `UNSUPPORTED` を返し、
  到達コードが M0 の 6 件のままであることを確認すること。
  変異試験として、guard の昇順取得・fencing 照合・receipt 必須・native lock 排他のいずれかを外すと
  対応する fixture が落ちることを確認すること。
  `python3 <リポジトリ>/scripts/release_check.py` が PASS すること。

- **備考**: 本タスクは M1-3 の出口判定そのものである。`M1-FLT-010`〜`015`、`017`、`018`、
  `021`〜`023`、`028`、`030` は M1-5（evidence 合成区分）の担当であり、ここには含めない。
