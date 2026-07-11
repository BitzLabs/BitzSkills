---
id: ENV-FR-009
version: 1.0
status: approved
domain: deploy
priority: medium
origin: SI-ENV-003（REV-001 operations OPS-201）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-009 env-init 生成物の復旧可能性

- **説明**: env-init が既存ファイル（settings.json / AGENTS.md / CLAUDE.md）を
  書き換える際、書き込みを取り消せる状態を保証しなければならない。展開先が
  git 管理下であることを推奨前提とし、git 管理外の場合はバックアップを取る。
- **受入基準 (EARS)**:
  - WHEN env-init が既存ファイルを書き換えようとする AND 展開先が git 管理外である THEN システムは書き込み前に対象ファイルの .bak バックアップを作成する SHALL
  - WHEN 展開先が git 管理下である THEN システムは git を復旧手段とみなし .bak を省略してよい SHALL
  - IF 展開先が git 未管理である THEN システムは書き込み前に git init を案内する SHALL
- **検証手段**: evals/env-init/（git 管理下/管理外での書き込み前状態のアサーション）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（SI-ENV-003 accepted による）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
