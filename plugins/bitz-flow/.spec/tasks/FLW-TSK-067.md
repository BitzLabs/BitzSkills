---
implements: FLW-FR-007, FLW-CON-006
depends_on: [FLW-TSK-066]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-006.md, plugins/bitz-flow/.spec/design/FLW-DSN-014.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/requirements/FLW-FR-007.md, plugins/bitz-flow/.spec/requirements/FLW-CON-006.md, plugins/bitz-flow/.spec/ROADMAP.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-067.md
status: done
---

### SI-FLW-054のM2運用規定を設計へ反映

- **作業内容**: reconnaissance上限、quarantine運用/read経路、承認疲れ、capability対称性、filesystem probe、永続証跡、脅威モデル、Activity API失敗分類を確定する。
- **検証**: `M2-FLT-051`〜`055`と要件EARSへ接続し、旧自動前進記述とbranch state表記も整合する。
