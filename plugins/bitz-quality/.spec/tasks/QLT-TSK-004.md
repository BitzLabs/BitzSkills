---
implements: [QLT-FR-008]
depends_on: [QLT-TSK-001, QLT-TSK-002, QLT-TSK-003]
boundary: plugins/bitz-quality/skills/quality-review/, plugins/bitz-quality/skills/quality-core/, tests/test_quality_review.py
status: done
---

### 再発防止ルール蓄積ループとquality-core統合

- **作業内容**: レビュー指摘事項からの `cause` / `general_rule` 抽出および `rules-ledger.md` への自律蓄積スクリプトを実装し、`quality-core` のセッション管理・オーケストレーションと統合する。
- **完了条件**:
  - `plugins/bitz-quality/skills/quality-review/SKILL.md` の作成
  - `plugins/bitz-quality/skills/quality-review/scripts/quality_rule_extractor.py` の実装
  - `plugins/bitz-quality/skills/quality-core/scripts/quality_session.py` の実装（セッションライフサイクル）
  - 全 pytest および release_check、spec_inspect が PASS すること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
