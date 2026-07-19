---
id: ENV-FR-012
version: 1.0
status: verified
domain: deploy
priority: medium
origin: SI-ENV-024
verification_method: manual-check
derived_from: ENV-FR-011
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-012 bitz-env-version 未記録環境の stamp 後付け救済（env-doctor 検出 + env-update 救済フロー）

- **説明**: env-init の stamp 機構（PR #74 / v0.7.0）以前に展開された環境は、レジストリ
  （`.claude/bitz-env.local.md`）に `bitz-env-version`（配置先バージョン D）の記録が無く、
  env-update（ENV-FR-011）が常に安全側停止して実質使えない。本要件は stamp の後付け救済パスを
  正式に規定する: env-doctor が欠如を検出して手順を提示し（読み取り専用のまま）、env-update が
  「記録なし」検出時に保守的な D 推定とユーザー確認を経て stamp して続行する救済フロー
  （SI-ENV-024 の案 (a)）を提供する（ENV-DSN-002 に基づく）。
- **受入基準 (EARS)**:
  - WHEN env-doctor がレジストリは存在するが frontmatter に `bitz-env-version` が無い環境を診断する THEN 欠如を WARN として検出し、env-update の救済フローによる stamp 後付け手順を修正案として提示すること SHALL
  - THE env-doctor は本診断において読み取り専用を維持し、stamp の書き込みを行わないこと SHALL
  - WHEN env-update がレジストリ存在かつ `bitz-env-version` 未記録を検出する THEN 即時の安全側停止ではなく救済フローへ分岐し、D の推定値・推定根拠・続行時の適用内容をユーザーへ提示すること SHALL
  - THE 救済フローの D 推定は保守的推定とすること SHALL（適用候補が最大になる最古側 = `references/migrations/` の最古ステップの `from`。ステップ不在時はマイグレーション適用なしの差分更新のみとし、過剰適用は CORE-CON-009 の guard 冪等性により no-op とする）
  - WHEN ユーザーが救済続行を承認する THEN 承認後の適用の最初にレジストリへ推定 D を stamp し、以降は ENV-FR-011 の正常系（D 比較→差分更新→マイグレーション→完了時 T stamp）と同一手順で続行すること SHALL
  - IF ユーザーが救済続行を承認しない THEN 一切書き込まず従来どおり安全側停止すること SHALL
  - IF レジストリ自体が存在しない THEN 救済フローの対象外とし、env-init の実行を案内して安全側停止すること SHALL
  - THE env-update の安全側停止の文言（SKILL.md / migration-runbook.md の「D 未記録」）は救済フローへの誘導を含むこと SHALL
- **検証手段**: 合成フィクスチャによる manual-check（`evals/` に記録）:
  (1) 記録なしレジストリを持つ模擬環境で env-doctor が WARN + 救済手順提示を行うこと、
  (2) 同環境で env-update が救済フロー（D 推定提示→承認→stamp→差分更新→T stamp）へ
  進めること、(3) レジストリ不在時に env-init 案内で停止すること、
  (4) doctor 実行前後でファイルが不変（読み取り専用）であること。
  + skill-validator チェックリスト通過 + release_check / spec_inspect PASS。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（draft 起票。SI-ENV-024 案 (a) 採用）
  - 1.0 (2026-07-19) approved（人間裁定）→ implementing 遷移（ENV-TSK-015 投入）
  - 1.0 (2026-07-19) verified 遷移（ENV-TSK-015 done、EARS 8項目実装、
    合成フィクスチャ検証 R1〜R4 PASS（`evals/env-update/stamp-rescue/`）、
    release_check PASS、spec_inspect --workspace 一括 PASS、pytest 236 green）
