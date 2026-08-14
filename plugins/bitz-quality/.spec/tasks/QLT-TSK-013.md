---
implements: QLT-FR-029
depends_on: [QLT-TSK-011, QLT-TSK-012]
boundary: plugins/bitz-quality/skills/quality-review/runtime/, plugins/bitz-quality/skills/quality-review/storage/, tests/test_quality_review_safety.py
status: pending
---

### レビュー実行安全性と世代fencing実装

- **作業内容**: timeout decision table、永続generation/fencing CAS、content-addressed read-only snapshot、single current pointer公開、raw log保護を実装する。
- **完了条件**: 任意timeoutのattempt隔離、必須timeoutのPASS禁止、旧writer拒否、snapshot escape・crash injection、manifest fsync後のpointer更新、last-known-good復旧、raw logのredaction/TTL/削除監査を検証し、pytestがPASSする。
