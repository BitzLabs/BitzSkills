---
id: QLT-FR-028
version: 1.0
status: draft
domain: quality-review
priority: high
origin: SI-QLT-002
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-028 公開API・schema・overrideの確定契約

- **説明**: CLI、JSON成果物schema、project overrideを実装者とconsumerが同じ契約で解釈できるよう固定する。
- **受入基準 (EARS)**:
  - WHEN CLIを呼び出す THEN `plan`・`run`・`validate`・`synthesize`・`import-sdd-review`・`compare`と必須引数、未知引数の非ゼロ終了を固定すること SHALL
  - WHEN成果物schemaを検証する THEN systemは型・required・enum・cardinality・未知field拒否・追加field方針をversionごとに適用すること SHALL
  - WHEN exit codeを返す THEN `0=PASS/valid`、`1=FAIL/invalid`、`2=BLOCKED/STALE/UNKNOWN`、`3=usage`を厳密に適用すること SHALL
  - WHEN project overrideを解決する THEN systemは`.spec/quality/review/`を正とし、base/overrideのdigest・owner・versionをmanifestへ記録すること SHALL
- **検証手段**: CLI contract、schema negative corpus、exit code matrix、override precedence fixtureで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
