---
implements: [ENV-FR-009, ENV-FR-010]
depends_on: []
boundary: plugins/bitz-env/skills/env-init/SKILL.md, plugins/bitz-env/skills/env-init/references/
status: done
---

### env-init の復旧可能性と生成物トラッキング

- **作業内容**: env-init SKILL.md（と references/）を更新する。
  (1) 書き込み前チェック: 展開先が git 管理外なら対象ファイルの .bak バックアップを作成し、
  git init を案内する。git 管理下なら .bak は省略してよい（ENV-FR-009）。
  (2) 生成物トラッキング: 生成ファイル一覧と既存ファイルへ書き込んだマーカー区間の位置を
  レジストリ `.claude/bitz-env.local.md` に記録する（ENV-FR-010）。
- **実施記録**: 2026-07-11 実施（v0.3.0、fast-worker 委譲・司令塔検収済み）。手順2（書き込み前チェック）・手順5（生成物トラッキング）を新設。
