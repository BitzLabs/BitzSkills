---
id: SDD-FR-159
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

### SDD-FR-159 未紐づけの P0/P1 指摘がある synthesis を PASS させない

- **説明**: レビューが自身の P1 を「別途 spec-issue 化を推奨」と書いたまま `PASS` を出し、
  起票されずに消えた（SI-SDD-031）。指摘が追跡先を持たないまま Gate を通ることを機械的に
  止める。**検査の置き場は `spec_inspect`** とする（裁定 D6）—— 判定は SDD-DSN-009 の
  コンテキスト1「仕様ライフサイクル」が持ち、コンテキスト6「可視化」は読み取り専用の
  読取モデルである。`sdd_report` に置くと「レポートを生成しなければ Gate を通せてしまう」
  構造になる。レビュー成果物はコンテキスト3「上流と設計」に属し、コンテキスト1 とは
  Customer-Supplier で結ばれているため、供給物の受け入れ検査を下流が持つのは自然である。
  設計の正は SDD-DSN-011。
- **受入基準 (EARS)**:
  - WHEN `spec inspect` が synthesis を検査する THEN `priority` が `P0` または `P1` で `tracked_by` を持たない finding を ID 付きで列挙し、不整合として報告すること SHALL
  - WHEN `verdict` が `PASS` の synthesis に未紐づけの P0/P1 が存在する THEN 当該 synthesis を不整合として報告し、検査全体を非ゼロで終了させること SHALL
  - WHEN `tracked_by` が spec-issue の ID を指す THEN 当該 spec-issue の実在を検査し、不在を幽霊参照として報告すること SHALL
  - WHEN `tracked_by` が `<REV-ID>:GP-NNN` 形式を指す THEN 当該レビューの `gate_preconditions` に同 ID が存在することを検査し、不在を幽霊参照として報告すること SHALL
  - WHEN 本検査を配置する THEN `spec_inspect` に置き、レポート生成（`sdd_report`）の実行有無に依存させないこと SHALL
  - WHEN `schema_version` を持たない既存レビューを検査する THEN 本検査の対象外とし、遡及的に不整合としないこと SHALL
  - WHEN `verdict` の算出式を扱う THEN 既存の閾値を変更せず、本検査は算出式と独立した検査として動作すること SHALL
- **検証手段**: `tests/test_spec_inspect.py`（未紐づけ P0/P1 の検出と非ゼロ終了、P2/P3 の
  非対象、`tracked_by` の spec-issue 実在検査と `GP-NNN` 実在検査、`schema_version` 不在時の
  検査除外）で unit-test する。`sdd_report` を実行しない条件下でも検出されることを検査する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。Design Gate 裁定3（2026-07-29）と
    SDD-DSN-011 の Design Gate 裁定（D6）から導出。
