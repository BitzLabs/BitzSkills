---
id: SDD-FR-162
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-SDD-036（裁定H。.spec/reports/decision-2026-07-30-order8-design-foundation.md）
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-162 設計成果物のID一意性を走査範囲と採番根拠で保証する

- **説明**: ID の一意性は `.spec/` スキーマの基礎であり、重複が無検出であることはトレーサビリティ
  全体の前提を崩す。`spec_inspect.py` の成果物レジストリ走査は `.spec/design` と
  `.spec/design/infra` の非再帰 glob に限られていたため、sdd-core が宣言する `design/stories/` の
  成果物が**重複 ID 検査と Traceability Matrix の両方から見えなかった**。同時に
  `spec_scaffold.py` の採番はファイル名から番号を抽出していたため、`domain-model.md`
  （`id: SDD-DSN-009`）のように **ID をファイル名に持たない成果物が採番から見えず**、
  既存 ID を再度払い出した。本要件は、走査範囲と採番根拠の両方を成果物の frontmatter に
  揃えることで、この2経路をふさぐ。`spec_inspect.py` の統合 preflight（`SDD-FR-144`）は
  すでに `rglob` で再帰走査しており、レジストリ走査だけが非再帰であった不整合を解消する。
  検査そのものは既存であり、本要件が変えるのは**検査が見える範囲**である。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `spec_inspect.py` が成果物レジストリを構築する THEN `.spec/design` 配下は
    サブディレクトリを含めて再帰的に走査すること SHALL
  - WHEN `.spec/design/stories/` のように `design` のサブディレクトリに成果物が存在する THEN
    その成果物は重複 ID 検査と Traceability Matrix の対象に含まれること SHALL
  - WHEN 同一 ID を持つ成果物が2つ以上存在する THEN `spec_inspect.py` は重複を検出して
    非ゼロ終了し、**衝突した全成果物のワークスペース相対パスを報告に含めること** SHALL
  - WHEN `spec_scaffold.py` が次番号を採番する THEN 番号の根拠は成果物の frontmatter の `id:`
    であり、ファイル名ではないこと SHALL
  - WHERE 成果物が frontmatter に `id:` を持たない場合 THEN `spec_scaffold.py` は
    ファイル名からの番号抽出へフォールバックし、既存 ID を見落とさないこと SHALL
  - WHEN `spec_scaffold.py` が `design` 種別を採番する THEN 走査範囲は
    `spec_inspect.py` のレジストリ走査と一致すること（`design` 配下を再帰する）SHALL
  - WHERE ファイル名が `_` で始まる成果物は、走査範囲の拡大後も従来どおり検査・採番の
    対象外であること SHALL
- **検証手段**: `tests/test_spec_inspect.py` と `tests/test_spec_scaffold.py` で unit-test する。
  (1) `design/stories/` の成果物が Traceability Matrix に現れること、(2) `design` の
  サブディレクトリ間で ID を重複させると FAIL し、報告に両方のパスが含まれること、
  (3) ID をファイル名に持たない成果物（`domain-model.md` 相当）とサブディレクトリの成果物を
  採番が数えること、(4) `_` 始まりのファイルが対象外のままであることを固定する。
  あわせて既存ワークスペース（ルート / bitz-env / bitz-flow / bitz-ddd / bitz-sdd /
  plugin-creator / skill-creator）を遡及的に FAIL させないことを
  `spec_inspect.py --workspace . plugins/*` の PASS で確認する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-036 と裁定H から導出。
    `SI-SDD-006` 提案2（frontmatter の `id:` を正とする採番）の実装を兼ねる。
  - 1.0 (2026-07-30) 代行可視化経路で approved 化
    （裁定記録 `.spec/reports/decision-2026-07-30-order8-design-foundation.md` 裁定H）。
  - 1.0 (2026-07-30) 実装・検証完了により verified 化。証跡
    `.spec/verification/pytest--5526358.json`（exit_code 0 / 132 passed）。
