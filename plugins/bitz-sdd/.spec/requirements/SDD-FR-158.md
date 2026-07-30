---
id: SDD-FR-158
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-SDD-031
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-158 ReviewFinding の schema を固定し finding ID をレビュー横断で一意にする

- **説明**: レビュー指摘（`findings[]`）は schema が機械検証されておらず、実測でレビューごとに
  キー集合がドリフトしていた。必要な項目を毎回その場で手作りしている状態であり、追跡の前提が
  成り立たない（SI-SDD-031、SDD-DSN-009 問題3）。本要件は `findings[]` の必須キーを固定し、
  レビュー内連番だった finding ID を `<REV-ID>:SYN-NNN` 形式でレビュー横断に一意化する
  （既に手で使われている形式の正式化であり移行を伴わない）。**物理形は synthesis JSON 内の
  配列のまま**とする — エンティティ性は同一性とライフサイクルの有無で決まり、ファイル分離を
  要求しない（裁定 D5）。既存レビューへは遡及しない（裁定 D8）。設計の正は SDD-DSN-011。
- **受入基準 (EARS)**:
  - WHEN `sdd-review` が synthesis を生成する THEN `findings[]` の各要素へ `id`・`priority`・`severity`・`source`・`title`・`recommendation`・`tracked_by`・`status` を持たせること SHALL
  - WHEN `findings[].id` を採番する THEN `<REV-ID>:SYN-NNN` 形式とし、レビュー横断で一意になること SHALL
  - WHEN `spec inspect` が `priority`・`severity`・`status` を検査する THEN それぞれ `P0`/`P1`/`P2`/`P3`、`critical`/`major`/`minor`/`info`、`open`/`tracked`/`resolved` の統制語彙に限定し、語彙外の値を不整合として報告すること SHALL
  - WHEN `spec inspect` が synthesis を検査する THEN `schema_version` を持つ synthesis のみ本 schema の検査対象とし、`schema_version` を持たない既存レビューは検査対象外として遡及的に不整合としないこと SHALL
  - WHEN 必須キーを欠く finding を含む synthesis を検査する THEN 欠落キーと finding ID を特定して不整合として報告すること SHALL
  - WHEN `findings[]` の物理配置を規定する THEN synthesis JSON 内の配列とし、finding ごとの個別ファイルを要求しないこと SHALL
  - WHEN `verdict` を算出する THEN 既存の閾値と算出式を変更しないこと SHALL
- **検証手段**: `tests/test_spec_inspect.py`（必須キー欠落の検出、統制語彙、`schema_version`
  不在時の検査除外、finding ID 形式）で unit-test する。`sdd-review` の
  `references/synthesis.md` が宣言する schema と検査実装が一致することを同テストで検査する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-031 と
    SDD-DSN-011 の Design Gate 裁定（D5・D8）から導出。
