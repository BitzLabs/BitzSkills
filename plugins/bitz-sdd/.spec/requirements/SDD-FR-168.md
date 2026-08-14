---
id: SDD-FR-168
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-FLW-052
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-168 ガバナンス主張の機械検証

- **説明**: 裁定済みという主張、topicごとのSSOT、設計とverified制約の整合を
  `.spec/governance-claims.json`へ明示し、`spec_inspect`でfail-closedに検査する。
- **受入基準 (EARS)**:
  - WHEN governance-claims.jsonが存在する THEN spec_inspectはschema_versionと配列構造を検査すること SHALL
  - WHEN 裁定済み主張を宣言する THEN spec_inspectは裁定記録と主張元の実在を検査すること SHALL
  - WHEN 同一topicに複数のauthoritative sourceを宣言する THEN spec_inspectは検査をFAILすること SHALL
  - WHEN 設計がverified/promoted制約とのconflictを宣言する THEN spec_inspectは検査をFAILすること SHALL
  - WHEN governance-claims.jsonが無い既存workspaceを検査する THEN spec_inspectは従来互換で検査を継続すること SHALL
- **検証手段**: 正常系、参照欠落、SSOT重複、未verified要件、conflict、任意導入互換をunit-testで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) SI-FLW-052の汎用3検査を要件化し、実装・検証
