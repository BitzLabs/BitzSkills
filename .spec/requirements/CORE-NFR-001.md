---
id: CORE-NFR-001
version: 1.0
status: approved
domain: tooling
priority: medium
origin: SI-CORE-021
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-NFR-001 委譲レジストリ整合の機械検証

- **説明**: 委譲レジストリと実体の整合を `release_check.py` / `spec_inspect.py` が機械検査し、
  モデル世代交代に伴う陳腐化を人間の目視ではなく機械で検出する。これが「更新できる仕組み」の本体。
- **受入基準 (EARS)**:
  - WHEN release_check.py または spec_inspect.py を実行する THEN 委譲レジストリに列挙された委譲先 agent が実在することを検査すること SHALL
  - WHEN 同検査を実行する THEN レジストリ外の対象文書に具体モデル名が直書きされていないことを検査すること SHALL
  - WHEN 同検査を実行する THEN レジストリのティア順序が整合（重複・欠落・循環がない）していることを検査すること SHALL
  - IF いずれかの整合検査に違反がある THEN 非ゼロで fail すること SHALL
- **検証手段**: tests/ に example-test を先行実装（テスト先行）。agent 実在・モデル名の外部直書き検出・
  ティア順序整合・違反時の非ゼロ終了を、正常系と各違反系のフィクスチャで検証する。
- **Revision History**:
  - 1.0 (2026-07-13) 初版（draft 起票）
