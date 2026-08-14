---
implements: [QLT-FR-011, QLT-FR-012]
depends_on: [QLT-TSK-005]
boundary: plugins/bitz-quality/skills/quality-trace/, tests/test_quality_trace.py
status: done
---

### quality-trace スキルおよびトレーサビリティ・証跡連携

- **作業内容**: `quality-trace` スキルを新規作成し、EARS 要件 ID とテストコードの自動トレーサビリティ照合スクリプトおよび検証証跡（verification evidence）生成スクリプトを実装する。
- **完了条件**:
  - `plugins/bitz-quality/skills/quality-trace/SKILL.md` の作成
  - `plugins/bitz-quality/skills/quality-trace/scripts/quality_trace.py` の実装
  - `tests/test_quality_trace.py` の実装と pytest PASS
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
