---
implements: FLW-NFR-012, FLW-NFR-006
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/guard.py, tests/test_flow_m1_guard.py
status: done
---

### target guardプロトコル（canonical化・昇順CAS取得・fencing照合・family lock順序）

- **作業内容**: `flowlib/guard.py` に target guard を実装する。guard key は
  `guard_identity × canonical_mutation_target` とし、**operation family を含めない**。

  - **canonical 化**: symlink・相対 path・case 差・別 worktree・remote alias を正規化して
    同一 target へ収束させる。raw path を key にしない。index は worktree ID を付加、
    remote は canonical host + provider repository ID + ref name のみから導出し
    local identity を混ぜない。**一意化できなければ副作用 0 で `BLOCKED`**。
  - **昇順 CAS 取得**: repo と全 target を canonical key の **bytewise 昇順**へ並べ、
    その順で取得する。逆順の要求は正規化するか、できなければ副作用 0 で拒否する。
    途中失敗時は**取得済み guard を逆順で解放**し、副作用 0 で `BLOCKED`。
  - **fencing token**: coordinator core が発行した単調増加 token を各 target に伴わせ、
    各副作用の直前に再照合する。Git storage 自体が token を原子的に検証するとは主張せず、
    local は OS exclusive lock と CAS、remote は server-side CAS を必須とする。
  - **family lock との順序**: **target guard を family 別 `concurrency_key` より先に取得**する。
    逆順の取得を許さない（順序が崩れると deadlock と二重 mutation の両方が起きうる）。
  - **既存 pending / quarantine の検査**: guard 内で検査し、存在する場合は**新しい intent を作らない**。
  - advisory lock / owner-only 永続領域 / fsync のいずれかを提供できない platform では
    write を `UNSUPPORTED` に落とす判定を返す。lock file の存在を所有証明にしない。

- **完了条件**: 上記の単体テストが PASS し、次の負の対照が拒否されること —
  逆順での guard 取得、family lock を先に取った状態からの guard 取得、
  fencing token 不一致での mutation、canonical 化できない target での続行、
  既存 pending / quarantine がある状態での新 intent 作成。
  `M1-FLT-005`（stage/commit cross-family 競合で同時 mutation 最大 1・敗者副作用 0）、
  `M1-FLT-006`（複数 target 逆順要求）、`M1-FLT-019`（symlink / case / worktree alias で
  同一 target へ収束）、`M1-FLT-024`（別 clone・worktree・remote alias から同一 remote ref）が
  期待どおりであること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: **公開 operation を増やさない**。M2 未完了の間は worktree-first の安全境界が
  閉じないため Git write を公開しない（`FLW-DSN-014` 縮退規則3）。本タスクは内部モジュールの
  実装と fault 検証にとどめ、dispatcher へ結線しない。
  lease と fencing token の発行元は coordinator core が正であり、ここで採番しない。
