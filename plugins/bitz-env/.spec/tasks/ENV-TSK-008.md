---
implements: [ENV-FR-005, ENV-FR-006]
depends_on: [ENV-TSK-006]
boundary: plugins/bitz-env/skills/env-orchestration/SKILL.md
status: done
---

### env-orchestration の防御的協調・レジストリ経由解決

- **作業内容**: env-orchestration SKILL.md を更新する。
  (1) 委譲先の解決をレジストリのルーティングテーブル経由に改め、固定スキル名を直接呼ばない。
  (2) 検収手順に「DIGEST のみに依存せず、中心が git diff / git status 等の客観的状態変化を
  自ら取得して検証する」ステップを追加する。
  (3) worker / advisor からのネスト委譲を禁止し、追加委譲の要否は中心のみが判断する旨を明記する。
- **実施記録**: 2026-07-11 実施（v0.3.0、fast-worker 委譲・司令塔検収済み）。「委譲先の解決（レジストリ経由）」節を新設。
