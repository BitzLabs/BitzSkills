---
implements: [QLT-FR-009, QLT-FR-010]
depends_on: []
boundary: plugins/bitz-quality/skills/quality-review/, tests/test_quality_review.py
status: done
---

### LLM多観点レビュー自動化と指摘レポート生成

- **作業内容**: `quality_llm_review.py` を実装し、アルダグラム流の11観点（L01〜L11: 仕様整合・エラー処理・境界値・セキュリティ・可読性等）の静的/LLMレビュー自動化と指摘レポート（Markdown）出力、`--auto-ledger` による再発防止台帳への自動登録を実装する。
- **完了条件**:
  - `plugins/bitz-quality/skills/quality-review/scripts/quality_llm_review.py` の実装
  - L01〜L11 のルール定義と重要度（P0〜P3）判定ロジック
  - `tests/test_quality_review.py` にレビュー自動化とレポート生成のテストを追加し全件 PASS
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
