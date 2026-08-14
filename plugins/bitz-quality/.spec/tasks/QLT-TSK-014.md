---
implements: QLT-FR-030
depends_on: [QLT-TSK-011, QLT-TSK-012, QLT-TSK-013]
boundary: plugins/bitz-quality/skills/quality-review/qualification/, plugins/bitz-quality/skills/quality-review/migration/, tests/test_quality_review_migration.py
status: implementing
---

### qualification移行rollback実装

- **作業内容**: adapter qualification、失効・再認定、dual-read/lossless export、golden corpus、rollback rehearsal、復旧bundle、二重Gate依存を実装する。
- **完了条件**: platform/keyごとの独立3 trial、green/red/stale/unknown fault matrix、変更時失効、移行観測期間・parity・rollback rehearsal・復旧bundleを検証し、point-of-no-return後をforward-fixとして扱い、sdd-review削除に両workspaceのGateを要求してpytestがPASSする。
