---
id: CORE-FR-014
version: 1.0
status: implementing
domain: governance
priority: medium
origin: SI-CORE-008
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-014 bitz-flow プラグインの新設（sdd-git の汎用化転記）

- **説明**: Git / GitHub 開発フロー（フロー選択・コミット規約・worktree 運用・
  Issue 駆動 PR フロー）を SDD 非採用プロジェクトでも使える独立プラグイン bitz-flow として
  新設する。本要件は**構造の新設と内容転記のみ**を保証し、既存 bitz-sdd（sdd-git を含む）の
  挙動は一切変えない（二重規定の解消は SI-CORE-010 で扱う）。
  起票時前提の再検証: SI-CORE-008 本文の「2マニフェスト」は SI-CORE-024（Codex 第3配布対象）
  以降の現行規約に合わせ**3マニフェスト**として実装する。
- **受入基準 (EARS)**:
  - THEN `plugins/bitz-flow/` が AGENTS.md の追加手順に従い3マニフェスト（name=bitz-flow、version 同値）と `skills/` を持ち、共有 marketplace.json に登録されること SHALL
  - THEN `skills/` に `flow-core`（フロー選択・コミット規約・失敗時復元）/ `flow-worktree`（worktree 並列運用）/ `flow-pr`（GitHub Issue 駆動 + Draft PR + squash merge + 未マージ依存の原則）の3スキルが存在し、sdd-git とその references の規定内容を SDD 非依存の表現で包含すること SHALL
  - THEN SDD 固有の接続点（Implements フッター、`.spec/tasks` / spec_inspect 連携、spec-issue 対応表）は各スキルの「bitz-sdd 併用時」節に隔離され、スキル本文が `.spec/` の存在を前提としないこと SHALL
  - THEN `plugins/bitz-flow/.spec/` が新設され、`discovery/` に SI-CORE-005 と同書式の6成果物（vision / metrics / scope / personas / positioning / assumptions、プレフィックス FLW-）と PROJECT.md を持つこと SHALL
  - THEN 本変更において sdd-git および既存5プラグインの実体 diff がゼロであること SHALL（共有 marketplace.json のエントリ追加を除く）
  - WHEN `python3 scripts/release_check.py` および `python3 scripts/spec inspect --workspace . plugins/*` を実行する THEN bitz-flow を含む全チェックが PASS すること SHALL
- **検証手段**: 本リポジトリで release_check.py（3マニフェスト整合・marketplace 整合・
  frontmatter 必須項目・CLI validate）と spec inspect（--workspace 一括）を実行し PASS を確認する。
  plugin-validator エージェントによる構造検証 PASS。既存プラグインの diff ゼロは
  `git diff --stat main` で確認する（example-test）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票。起票時前提の乖離1件 — 2→3マニフェスト — を説明欄に明記）
