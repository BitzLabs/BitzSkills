---
implements: [ENV-FR-001, ENV-FR-002, ENV-CON-001]
depends_on: []
boundary: plugins/bitz-env/scripts/env_guard.py, plugins/bitz-env/hooks/hooks.json, plugins/bitz-env/hooks.json
status: done
---

### ガードレール即効層（env_guard.py + 両対応フック）の実装

- **作業内容**: 破壊的操作5種を deny する共通ガードスクリプトと、Claude Code
  （hooks/hooks.json、ラッパー形式）・Antigravity（ルート hooks.json、camelCase）
  両対応のフック定義を実装する。stdin の JSON 形状でプラットフォームを自動判別し、
  不正入力は fail-open で素通しする。deny 対象は普遍的最小集合に限定する。
- **実施記録**: 2026-07-11 実施（v0.1.0、コミット e95834a）。手動8ケーステスト PASS。
  sudo パターンの取り逃し1件を実装中に検出・修正済み。
- **備考**: reverse-derived（実装先行）。pytest 正式化は別タスク。
