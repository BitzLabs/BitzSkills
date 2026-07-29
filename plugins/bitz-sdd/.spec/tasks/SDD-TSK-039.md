---
implements: SDD-FR-149
depends_on: []
boundary: skills/sdd-docs/scripts/sdd_sync.py, skills/sdd-docs/SKILL.md, skills/sdd-discovery/SKILL.md, skills/sdd-discovery/references/scope.md, tests/test_sdd_sync.py
status: done
---

### Discovery成果物の同期マッピングを網羅する

- **作業内容**: `DEFAULT_MAPPING` に metrics / constraints / personas / positioning の4対を
  追加し、Discovery 6成果物を 1:1 で網羅する。制約は `scope.md` から独立させて
  `.spec/discovery/constraints.md` を同期元とし、その理由（push の逆反映先が決まらない）を
  sdd-discovery の SKILL.md と references/scope.md に明記する。pull / push それぞれの
  欠損時 SKIP と diff の網羅を unit-test で固定する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
