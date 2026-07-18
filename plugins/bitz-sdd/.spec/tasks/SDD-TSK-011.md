---
implements: SDD-FR-125
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-docs/assets/docs-templates, plugins/bitz-sdd/skills/sdd-docs/scripts/docs_inspect.py, tests/test_docs_inspect.py
status: implementing
---

### 日本語6章テンプレートと構造検査

- **作業内容**: 必須6章と任意referenceテンプレートを構成し、章-area対応、任意章宣言、
  管理対象外、旧章混在、project_typeをstrict検査するテストと実装を追加する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
