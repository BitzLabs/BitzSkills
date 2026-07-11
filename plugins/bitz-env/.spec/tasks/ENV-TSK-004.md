---
implements: [ENV-FR-001, ENV-FR-002]
depends_on: []
boundary: tests/test_env_guard.py
status: done
---

### ガード契約の pytest 正式化

- **作業内容**: v0.1.0 実装時の手動8ケーステストを、要件の EARS 節に対応する
  pytest（tests/test_env_guard.py）として正式化する。deny 5種 × 両プラットフォーム、
  pass ケース（誤検知なし）、形状判別、不正入力の fail-open を網羅する。
- **実施記録**: 2026-07-11 実施。.venv/bin/pytest tests/test_env_guard.py PASS。
- **備考**: EARS 節との対応はテスト内の docstring に要件 ID で記載する。
