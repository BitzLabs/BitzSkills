---
id: SI-CORE-006
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 4-1。docs/improvement_master_plan.md）
target: plugin-creator（共通ライフサイクルスキル標準の不在）と ルート CORE-CON 規約
proposed_change_type: new
status: accepted
---
- **目的**: 全プラグインに共通するライフサイクル操作を標準スキル名
  `<plugin名>:init` / `doctor` / `update` / `uninstall` として制定し、
  プラグインごとの独自命名の乱立を防ぐ。独自スキルは従来の命名規則を維持する。
- **提案する修正**:
  1. plugin-creator に標準仕様 reference（各スキルの責務・最小契約・雛形）を追加する。
     最小契約: init=初期設定と依存確認、doctor=環境診断（読み取り専用）、
     update=バージョン更新と依存再確認、uninstall=痕跡を残さない撤去
  2. ルート `.spec/requirements/` に CORE-CON draft を起票する（approved 化は人間）
  3. 先行実装の bitz-env（env-init / env-doctor / env-destroy）の扱いを裁定材料として併記する
     （env-destroy → uninstall への改名 or 別名維持は人間裁定。本 ISSUE では改名しない）
- **対象ファイル**: `plugins/plugin-creator/skills/plugin-structure/references/`（または新規
  reference）、`.spec/requirements/CORE-CON-007.md`（draft）、plugin-creator のマニフェスト bump。
- **確認観点**:
  - 規定のみで既存スキルの変更が無いこと（動作変更ゼロ）
  - release_check / spec_inspect PASS
- **影響推定・ロールバック**: 規約文書と draft 要件の追加のみ。単独 revert 可能。
- **依存**: なし（SI-CORE-004/005 と並行可）。
- **裁定（2026-07-13, 人間）**: bitz-env の **env-destroy → env-uninstall へ改名**を採用（本文の「改名しない」方針から変更）。標準名 uninstall に合わせる。改名は bitz-env への波及（参照・ドキュメント更新＋bump）を伴うため、006 実装時に bitz-env ワークスペースへ委任して扱う。
