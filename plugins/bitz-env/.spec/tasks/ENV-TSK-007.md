---
implements: [ENV-FR-006]
depends_on: [ENV-TSK-006]
boundary: plugins/bitz-env/skills/env-register/SKILL.md
status: done
---

### env-register の役割ルーティング対応

- **作業内容**: env-register SKILL.md を契約 v2 に合わせて更新する。
  登録時に「役割→実スキル名」のルーティングテーブルを `.claude/bitz-env.local.md` に記録する。
  既登録アダプタとのスキル名衝突を検出し、アダプタ名プレフィックスによる名前空間化と
  優先順の明示で解決する手順を追加する。v1 固定名アダプタは自明ルーティングとして登録する。
- **実施記録**: 2026-07-11 実施（v0.3.0、fast-worker 委譲・司令塔検収済み）。レジストリを routes + priority 形式に更新。
