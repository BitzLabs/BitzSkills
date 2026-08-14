---
implements: FLW-CON-001, FLW-CON-002
depends_on: [FLW-TSK-065]
boundary: plugins/bitz-flow/.spec/governance-claims.json, plugins/bitz-flow/.spec/tasks/FLW-TSK-066.md
status: done
---

### bitz-flowのガバナンス主張を機械可読化

- **作業内容**: SI-FLW-052裁定に従い、M2是正の裁定根拠、topic別SSOT、設計とverified制約の整合を`governance-claims.json`へ登録する。
- **検証**: bitz-sdd 3.15.0のspec_inspectで全参照の実在、SSOT一意性、verified制約との非競合を確認する。
