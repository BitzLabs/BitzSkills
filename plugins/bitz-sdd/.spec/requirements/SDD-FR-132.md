---
id: SDD-FR-132
version: 1.0
status: verified
domain: verification
priority: medium
origin: SI-CORE-015
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-132 ワークスペース間 spec-issue 委託フローの正式化と機械検証

- **説明**: ルート SPEC とサブ（ワークスペース）SPEC 間の spec-issue 委託を、
  frontmatter（`origin:` / `delegated_to:`）と lifecycle.md の規定 + spec_inspect.py の
  横断検証で正式なフローにする。現状は SI-CORE-031/032 等で書式がデファクト運用されて
  いるが規定が無く、リンク切れ・双方向記録漏れを機械検出できない。
  委託の方向は「サブ→ルート = エスカレーション」「ルート→サブ = 委任」の2方向のみとし、
  **サブ↔サブの直接委託は認めない（常にルート経由）**（裁定 2026-07-19:
  SI-CORE-015 原文の dependencies 例外条項は不採用。複数サブに影響する問題は
  ルートで管理し各サブへ依頼を出す構成に単純化する）。
- **受入基準 (EARS)**:
  - WHEN spec-issue の frontmatter に `delegated_to:`（`<ws>:<ID>` カンマ区切り）が記載された状態で spec_inspect を実行した THEN 各エントリの ID 部が検証対象ワークスペース群の既知 ID（要件・spec-issue・タスク）に実在することを検査し、実在しなければ FAIL として報告すること SHALL
  - WHEN `delegated_to:` の委託先 ID のファイルが実在する THEN その frontmatter の `origin:` テキストに委託元 spec-issue ID への言及があることを検査し、言及が無ければ双方向リンク欠如として FAIL すること SHALL
  - WHEN `origin:` / `delegated_to:` を持たない既存 spec-issue を検証した THEN 委託チェックは適用されず従来どおり PASS すること SHALL（後方互換）
  - WHEN `origin:` に注記付きの値（例: 起票ワークスペース名 + 括弧書きの由来）が記載されている THEN 委託チェックはこれを容認し FAIL しないこと SHALL
  - WHEN spec_scaffold.py で spec-issue を生成する際に `--origin` / `--delegated-to` を指定した THEN 生成される frontmatter に反映されること SHALL
  - WHEN lifecycle.md を参照した THEN 委託フロー（サブ→ルート エスカレーション / ルート→サブ 委任 / サブ↔サブ 禁止・ルート経由 / ルート SPEC 不在時はルート `.spec/` 作成から）と frontmatter 書式が規定されていること SHALL
- **検証手段**: tests/test_spec_inspect.py の example-test（後方互換 PASS・
  リンク切れ FAIL・双方向欠如 FAIL・注記付き origin 容認・正常委託 PASS）と
  tests/test_spec_scaffold.py（委託フィールド生成）。本リポジトリの
  `spec inspect --workspace . plugins/*` 一括検証が PASS すること。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（SI-CORE-015 委任起票。チャット裁定によりサブ↔サブ
    直接委託の例外条項を不採用としてルート経由に一本化）
