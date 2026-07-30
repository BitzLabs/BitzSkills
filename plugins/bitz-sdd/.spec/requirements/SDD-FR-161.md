---
id: SDD-FR-161
version: 1.0
status: approved
domain: verification
priority: high
origin: SI-SDD-031
verification_method: unit-test
derived_from: SDD-FR-158
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-161 gate_preconditions に kind と basis を必須化し assumed を blocking の根拠にしない

- **説明**: レビューの `gate_preconditions` は「Gate 通過前に消化する条件」と「Gate で決める論点」を
  区別しておらず、前提条件なのに Gate で決めることという循環を起こした（裁定記録が自ら
  認めている）。さらに**未検証の想定が前提条件として最先行タスクを規定した事故**も起きている。
  本要件は `kind`（`blocking` / `agenda`）と `basis`（`verified` / `assumed`）を必須化し、
  **`basis: assumed` を根拠に `kind: blocking` を立てられない**ことを不変条件として機械検証する。
  Gate 通過の阻止に使うのは `kind: blocking` かつ未消化のものだけとする。既存レビューへは
  遡及しない（裁定 D8）。設計の正は SDD-DSN-011（裁定 D7）。
- **受入基準 (EARS)**:
  - WHEN `gate_preconditions[]` を記述する THEN 各要素へ `kind`（`blocking` または `agenda`）と `basis`（`verified` または `assumed`）を持たせること SHALL
  - WHEN `spec inspect` が `gate_preconditions[]` を検査する THEN `kind`・`basis` の欠落と統制語彙外の値を不整合として報告すること SHALL
  - WHEN `basis` が `assumed` の前提条件に `kind: blocking` が指定された THEN 不変条件違反として不整合に報告し、検査を非ゼロで終了させること SHALL
  - WHEN Gate 通過可否を機械判定する THEN `kind` が `blocking` かつ未消化の前提条件のみを通過阻止の根拠に用い、`kind: agenda` は通過阻止に用いないこと SHALL
  - WHEN 前提条件を `basis: verified` と記述する THEN その根拠となる実測の所在を参照として持たせ、不在を不整合として報告すること SHALL
  - WHEN `schema_version` を持たない既存レビューを検査する THEN `kind`・`basis` の欠落を不整合としないこと SHALL
- **検証手段**: `tests/test_spec_inspect.py`（`kind`・`basis` の必須化と統制語彙、
  `assumed` × `blocking` の不変条件違反検出、`agenda` が通過阻止に使われないこと、
  `schema_version` 不在時の検査除外）で unit-test する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-031 提案2 と
    SDD-DSN-011 の Design Gate 裁定（D7）から導出。
