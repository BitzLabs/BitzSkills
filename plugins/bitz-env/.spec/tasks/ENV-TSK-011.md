---
implements: [ENV-CON-004, ENV-NFR-002]
depends_on: []
boundary: plugins/bitz-env/skills/env-doctor/SKILL.md, plugins/bitz-env/README.md, plugins/bitz-env/rules/
status: done
---

### ガードの位置づけ明記と rules 注入サイズの節度

- **作業内容**:
  (1) env-doctor SKILL.md: env-init 未実行で permissions 層が無い場合に WARN として
  報告する診断項目を追加する（ENV-CON-004）。
  (2) README / env-doctor SKILL.md: ガードは「誤操作抑止でありセキュリティ境界ではない」旨を
  明示する（既述箇所は確認のみ）。
  (3) README または rules/ 冒頭: rules 注入はガードレール本文に限定し肥大化を避ける方針を
  明文化する（ENV-NFR-002。manual-check なので方針の明文化と現状サイズの確認まで）。
- **実施記録**: 2026-07-11 実施（v0.3.0、fast-worker 委譲・司令塔検収済み）。WARN 診断項目を追加、位置づけ・節度方針は README と env-doctor に追記（rules/ は変更なし）。
