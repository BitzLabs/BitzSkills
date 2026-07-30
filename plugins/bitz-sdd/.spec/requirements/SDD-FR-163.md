---
id: SDD-FR-163
version: 1.0
status: implementing
domain: reporting
priority: high
origin: SI-SDD-034（裁定J。.spec/reports/decision-2026-07-30-order8-design-foundation.md）
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-163 未完了成果物があるフェーズ判定で done を返さない

- **説明**: `spec_status.py` の `determine_phase()` は、完了済みの要件・タスク群と新しい
  `draft` 要件が同じ workspace に併存すると、未承認要件が残っていても
  `phase_code: done`（Promotion Gate 待ち）を返した。旧系列の `verified` 要件があり旧タスクが
  すべて `done` なら `n_ver == n_appr` が成立し、新系列の `draft` 要件の存在が判定へ入らない
  ためである。`next_actions` は同時に「draft 要件が N 件 — 承認（approved 化）を行う」を
  返すため、**フェーズ表示と次アクションが異なる工程を示し**、エージェントが Plan 工程を
  飛ばして Promotion Gate へ進むおそれがある。

  本要件は「`done` は未完了成果物が存在しないときだけ返す」を不変条件として定義する。
  修正は**加算的**であり、`SDD-FR-136` が定めた `phase_code` の7語彙は削除・改名しない
  （返る値は既存語彙のいずれかであり、変わるのは値の分布だけである）。feature・世代単位で
  フェーズを集計する案は V4 の Workspace 責任モデルと接するため採らない（裁定J）。
  本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `draft` 要件が1件以上ある THEN `determine_phase()` は `done` を返さないこと SHALL
  - WHERE `verified` 要件と `done` タスクだけの完了済みワークスペースへ `draft` 要件を
    追加した場合 THEN `phase_code` は `plan` になること SHALL
  - WHEN `draft` 要件が存在しない従来の完了状態である THEN `phase_code` は `done` を
    維持すること SHALL
  - WHEN `phase_code` と `next_actions` を同時に出力する THEN 両者が異なる工程を
    案内しないこと SHALL（`done` を返すときは承認・実装・検証の未処理を促す
    次アクションを含まないこと）
  - WHERE 要件が `draft` → `approved` → `implementing` → `verified` と進む THEN
    `phase_code` は後退せず `plan` → `execute`（タスク未完了時）→ `verify` → `done` の
    順序で進むこと SHALL
  - THEN `phase_code` の値集合は `SDD-FR-136` の7語のままであること SHALL
- **検証手段**: `tests/test_spec_status.py` で unit-test する。(1) `verified` 要件＋`done`
  タスクのベースラインへ `draft` 要件を追加した状態が `done` にならず `plan` になること、
  (2) `draft` が無い完了状態が `done` を維持すること、(3) `done` を返すときの
  `next_actions` に承認・実装・検証の未処理項目が現れないこと、(4) status を進めたときの
  フェーズ順序を固定する。`tests/test_spec_labels.py` と `scripts/release_check.py` の
  フェーズ語彙照合が PASS することで語彙の不変を確認する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-034 と裁定J から導出。
    `SDD-FR-136` のフェーズ語彙・後方互換方針を維持したまま判定を厳密化する。
