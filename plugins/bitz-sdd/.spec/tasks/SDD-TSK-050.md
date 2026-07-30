---
implements: SDD-FR-161
depends_on: [SDD-TSK-047]
boundary: skills/sdd-core/scripts/spec_inspect.py, skills/sdd-review/references/synthesis.md, tests/test_spec_inspect.py
status: done
---

### gate_preconditions に kind と basis を必須化する

- **作業内容**: `gate_preconditions[]` に `kind`（`blocking` / `agenda`）と
  `basis`（`verified` / `assumed`）を必須化し、`basis: verified` には実測の所在
  （`evidence`）を求める。**`basis: assumed` を根拠に `kind: blocking` を立てられない**ことを
  不変条件として検査し、違反は非ゼロ終了させる。Gate 通過の阻止に使うのは
  `kind: blocking` かつ未消化のものだけとする。`schema_version` を持たない既存レビューでは
  欠落を不整合としない。`synthesis.md` に区別の意味と不変条件を記す。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
