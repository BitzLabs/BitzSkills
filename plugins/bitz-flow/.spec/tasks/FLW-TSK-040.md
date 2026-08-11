---
implements: FLW-FR-005, FLW-NFR-003
depends_on: [FLW-TSK-039]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/commit_causality.py, tests/test_flow_m1_commit_causality.py
status: done
---

### git.commitのREC-COMMIT因果証跡

- **作業内容**: `flowlib/commit_causality.py` に REC-COMMIT を実装する。
  **原則: 「一致する commit を後から検索して今回の成功と見なす」ことをしない。**

  手順（Adapter → Intent Store → Git Object DB → Ref Store）:

  1. HEAD / index / tree / message / author / 時刻 / sign 方式を固定する。
  2. canonical commit bytes と `planned_commit_oid` を**副作用なしで**計算する。
  3. `old_oid` / `planned_oid` / `operation_id` / fencing token を
     **pre-object intent** として保存し fsync する。
  4. canonical bytes を planned OID で object store へ保存する。
  5. fencing 照合後に `update-ref old_oid -> planned_oid`（CAS）を行う。
  6. CAS result（before / after oid）を同じ operation chain へ receipt として追記し fsync する。
  7. ref を再照合し、`DONE` receipt または quarantine を追記する。

  - **`DONE` の条件**: CAS を実行した writer の receipt、old / planned / after OID、現在 ref、
    intent chain が**すべて一致**すること。**ref が planned OID でも receipt が無ければ
    `DONE` へ昇格させず `INDETERMINATE`** とする。
  - object store への保存は reachable ref を変えないが副作用であり、必ず pre-object intent の
    fsync 後に行う。object 保存前 crash は object 不存在の照合で `abandoned-no-effect`、
    object 保存後・CAS 前 crash は同一 OID の存在と ref 不変を照合して人間裁定へ回す
    （`orphan-object-no-reachable-effect`。**object は削除しない**）。
  - commit message は Conventional Commits と任意の WorkUnit / Implements footer を事前検査する。
  - 署名実装が副作用なしに canonical bytes を確定できない platform では commit を `UNSUPPORTED` とする。

- **完了条件**: 実 Git リポジトリを使う単体テストが PASS し、次が確認できること —
  receipt を欠く場合に `DONE` ではなく `INDETERMINATE` になること、
  `PARTIAL` が構築されないこと（単一 ref CAS の原子性により到達不能）、
  CAS 不成立時に副作用 0 を証明できた場合だけ intent を解除すること、
  同一 parent / tree / message の別 commit を「今回の成功」と誤帰属しないこと。
  `M1-FLT-003`（commit CAS 直後 crash）、`M1-FLT-016`（pre-object intent 直後 / object 保存直後 crash）、
  `M1-FLT-026`（object 保存後・CAS 前 crash で orphan-object 結論、object 保持のまま承認解除）が
  期待どおりであること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: **公開 operation を増やさない**（`FLW-DSN-014` 縮退規則3）。dispatcher へ結線せず、
  `git.commit` は引き続き `UNSUPPORTED` を返す。
