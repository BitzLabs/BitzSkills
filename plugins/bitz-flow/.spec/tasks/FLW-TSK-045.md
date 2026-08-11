---
implements: FLW-FR-011
depends_on: [FLW-TSK-044]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/doctor.py, tests/test_flow_m1_doctor.py
status: pending
---

### repo.doctor v2（operation別capability診断）

- **作業内容**: `flowlib/doctor.py` に v2 の環境診断を実装する。対象 project へ**書き込まない**。

  - Python・Git・gh・repository・remote・default branch・認証 host を**読み取り専用**で診断する。
  - **operation 別 capability** を返す: 必要 version、scope、filesystem、locking、process tree 収束。
    write operation については advisory lock・owner-only 領域・fsync・atomic rename・
    native index lock・remote CAS の可否を個別に返す。
  - 前提が不足する場合は**不足 stage・許可語彙 cause・導入または設定の next action**を返す。
  - 診断対象が GitHub を使わない場合、`gh` の欠如は **warning** として返す（失敗にしない）。
  - 共通 envelope schema を満たす（`flow-core` と同じ result 契約）。
  - 診断結果に絶対 path・token・URL userinfo を載せない（sanitizer を通す）。

- **完了条件**: 単体テストが PASS し、次が確認できること —
  依存欠如・未認証・remote 欠如・unsupported filesystem のそれぞれで
  不足 stage と許可語彙 cause が返ること、対象 project に副作用が 0 であること、
  GitHub 非利用時に `gh` 欠如が warning になること、診断出力に秘密値・絶対 path が現れないこと。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: **公開 operation を増やさない**（M2 未完了のため）。v1 の flow-doctor スキルは
  そのまま残し、本タスクは v2 の内部実装にとどめる。
