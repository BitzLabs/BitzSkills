---
id: ENV-FR-013
version: 1.0
status: verified
domain: deploy
priority: medium
origin: SI-ENV-025
verification_method: manual-check
derived_from: ENV-FR-011
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-013 env-update dry-run の git 管理状態実確認と rollback 手段の正確な提示

- **説明**: env-update の書き込み前承認フロー（手順4）は rollback 用バックアップ先の提示を
  求めるが、書き込み対象が git 管理下かどうかの確認手順が無く、手順5.1 のバックアップ分岐
  （git 管理外 = `.bak` / 管理下 = git）と実行時に接続されていない。ENV-FR-012 救済フローの
  実地試行（SI-ENV-025）で、gitignore されたレジストリ `.claude/bitz-env.local.md` に対して
  「rollback 手段は git」と誤提示し `.bak` 取得がスキップされた。本要件は dry-run 時に
  変換対象ファイルごとの git 管理状態を**実際に確認**して対応する rollback 手段を提示し、
  git 管理外の対象への適用時に `.bak` バックアップ取得を必須とすることを規定する。
- **受入基準 (EARS)**:
  - WHEN env-update が手順4 の dry-run を提示する THEN 変換対象ファイルごとに git 管理状態を `git ls-files` / `git check-ignore` 等のコマンドで実際に確認し、その結果（管理下 / 管理外・ignore）と対応する rollback 手段（管理下 = git / 管理外 = `.bak` 取得）を対にして提示すること SHALL
  - THE dry-run の git 管理状態の提示は実確認の結果のみに基づくこと SHALL（「リポジトリ内のパスだから git 管理下」等の推測・既定値での提示を禁止する）
  - WHEN 承認後の適用（手順5）で git 管理外の対象へ書き込む THEN 書き込み前に `<ファイル名>.bak` バックアップを必ず取得すること SHALL
  - THE SKILL.md は、レジストリ `.claude/bitz-env.local.md` が env-init の既定で gitignore 対象（ローカルファイル）となり「リポジトリ内 = git 管理下」の推定が成り立たない旨を注記すること SHALL
  - THE migration-runbook.md の承認フロー記述は SKILL.md 手順4 の git 管理状態実確認と同期していること SHALL
- **検証手段**: manual-check（`evals/env-update/` に記録）:
  (1) SKILL.md 手順4 に対象ファイルごとの git 管理状態実確認と rollback 手段の対提示が
  規定されていること、(2) 手順5.1 の `.bak` 分岐が手順4 の確認結果と接続されていること、
  (3) gitignore されたレジストリを持つ環境（本リポジトリ相当）の机上トレースで
  「rollback 手段は git」の誤提示が再発しないこと。
  + release_check / spec_inspect PASS。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（draft 起票。SI-ENV-025 由来）
  - 1.0 (2026-07-19) approved（人間裁定）→ implementing 遷移（ENV-TSK-016 投入）
  - 1.0 (2026-07-19) verified 遷移（ENV-TSK-016 done、EARS 5項目実装、
    合成フィクスチャ検証 G1〜G4 PASS（`evals/env-update/dryrun-rollback/`）、
    release_check PASS、spec_inspect --workspace 一括 PASS、pytest 236 green）
