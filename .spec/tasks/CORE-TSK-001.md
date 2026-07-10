---
implements: CORE-FR-001
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-design/SKILL.md
status: done
---

### sdd-design 成果物表に必須/任意を明示（タスク ID はファイル名が正）

- **作業内容**: 成果物定義表に「必須/任意」列を追加し、各行の条件（API を公開するシステムのみ等）を明記する。文言のみの変更で同期マッピング・スクリプトには触れない。
- **実施記録**: 2026-07-11 実施（Phase 8b PR 内）。sdd-design 0.4.1 / bitz-sdd を patch bump。
- **備考**: 軽量レーン適用（spec-issue → 要件 → タスクのみ。discovery / design スキップ）。
  要件 CORE-FR-001 は draft のまま — approved / verified への遷移は人間裁定後。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
