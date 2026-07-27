---
id: CORE-FR-002
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-002（Phase 8b 実演サイクル中の発見）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-002 spec_inspect の自己言及 ID の幽霊参照除外

- **説明**: spec_inspect.py の参照走査は、ファイル自身の ID（ファイル名 stem と一致する ID）を参照として数えない。タスクファイルが自分のタスク ID を frontmatter・見出しに書いても幽霊参照と誤検知しない。
- **受入基準 (EARS)**:
  - WHEN タスクファイルが自身の ID を本文に含む THEN spec_inspect は当該 ID を幽霊参照として報告しないこと SHALL
  - WHEN タスクファイルが存在しない要件 ID を参照する THEN spec_inspect は幽霊参照として FAIL を報告 SHALL
- **検証手段**: tests/test_spec_inspect.py（自己言及の非検出 + 真の幽霊参照の検出継続）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（SI-CORE-002 の要件化。人間裁定はチャット指示 → 実装・example-test 合格により verified）
