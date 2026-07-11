---
implements: [ENV-CON-002]
depends_on: []
boundary: plugins/bitz-env/skills/env-orchestration/references/collab-contract.md
status: done
---

### 協調アダプタ契約 v1（collab-contract.md）の制定

- **作業内容**: 標準スキルセット（delegate 必須 / review 推奨 / status 任意）、
  能力宣言（metadata.collab または collab.json）、DIGEST 報告形式を公開契約として
  文書化する。既存 antigravity プラグインの実構成を後方互換で一般化する。
- **実施記録**: 2026-07-11 実施（v0.1.0、コミット e95834a）。
- **備考**: 本契約の変更は Design Gate 対象・軽量レーン禁止（PROJECT.md 公開契約節）。
