---
implements: QLT-FR-028
depends_on: [QLT-TSK-010]
boundary: plugins/bitz-quality/skills/quality-review/schema/, plugins/bitz-quality/skills/quality-review/cli/, tests/test_quality_review_contract.py
status: implementing
---

### レビューAPI schemaとCLI契約実装

- **作業内容**: plan/run/validate/synthesize/import-sdd-review/compareのCLI契約、閉集合JSON schema、exit code、`.spec/quality/review/` override解決を実装する。
- **完了条件**: 必須引数・未知引数・型・required・enum・cardinality・未知field、exit code 0/1/2/3、base/override digest・owner・versionと優先順位を契約fixtureで検証し、pytestがPASSする。
- **備考**: schemaの追加field方針はversioned contractとして扱い、独断で緩和しない。
