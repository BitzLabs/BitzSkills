---
implements: CORE-CON-001, CORE-CON-002, CORE-CON-003, CORE-CON-004, CORE-CON-005, CORE-CON-006
depends_on: []
boundary: tests/, .github/workflows/ci.yml, scripts/release_check.py, scripts/bump_version.py
status: done
---

### リポジトリ規約の検証基盤（reverse-derived の完了タスク）

- **作業内容**: 各規約要件の検証手段は Phase 0〜7a で実装済み（pytest 19件 / release_check.py /
  CI の test + pr-title ジョブ / skill-validator チェックリスト）。本タスクはそれらを
  implements として要件に紐づける逆起票の記録であり、新規の実装作業はない。
- **実施記録**: 2026-07-11 起票（要件の approved 化と同時）。
- **備考**: タスク ID はファイル名が正（本文に ID を書かないのは SI-CORE-002 の回避策）。
