---
id: CORE-FR-016
version: 1.0
status: approved
domain: governance
priority: medium
origin: SI-CORE-010
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-016 sdd-git の縮退（Git フローの正を bitz-flow へ一本化）

- **説明**: SI-CORE-008/009 で bitz-flow が実用可能になったことを受け、bitz-sdd の sdd-git を
  薄い委譲ポインタに縮退し、Git フローの規定の正を bitz-flow に一本化する（動作変更のみ）。
  人間裁定（2026-07-13）どおり**縮退維持（minor bump）**とし、完全廃止（major）はしない。
  sdd-git にはフロー選択の判断表と SDD 固有の接続点（Implements フッター・タスク並列投入条件）
  だけを残し、実行手順は bitz-flow の flow-core / flow-worktree / flow-pr への参照に置換する。
  起票時前提の再検証: SI-CORE-010 本文の「2マニフェスト」は SI-CORE-024 以降の現行規約に
  合わせ**3マニフェスト**（.claude-plugin / plugin.json / .codex-plugin）として実装する。
- **受入基準 (EARS)**:
  - THEN `plugins/bitz-sdd/skills/sdd-git/SKILL.md` が縮退され、フロー選択の判断表と
    SDD 固有の接続点（Implements フッター書式・`.spec/tasks` の並列投入条件）のみを保持し、
    worktree・PR の実行手順は bitz-flow の該当スキル名への参照で示すこと SHALL
  - THEN sdd-git の references/ にあった実行手順の詳細は削除または bitz-flow への参照に
    置換され、同一規定の二重記載が残らないこと SHALL
  - THEN bitz-sdd の3マニフェストすべてに `metadata.dependencies` として bitz-flow への
    依存が同値で宣言されること SHALL（SI-CORE-007 の依存グラフ検証機構を利用）
  - THEN `grep -rn "sdd-git" plugins/ .spec/ docs/` の結果が、更新済みの参照または
    意図を明記した残置のみであること SHALL（sdd-core の parallel-git.md・sdd-implement 等の
    参照先記述の更新を含む）
  - WHEN `python3 scripts/release_check.py` を実行する THEN 依存グラフ検証（依存先実在・semver 制約・3マニフェスト同値）を含む全チェックが PASS すること SHALL
  - WHEN bitz-sdd を bump する THEN minor bump であること SHALL（裁定: 縮退維持）
- **検証手段**: release_check.py の実行で依存宣言と bump を確認し、
  `grep -rn "sdd-git"` の全ヒットを目視分類（更新済み / 意図した残置）して記録する。
  sdd-git SKILL.md の縮退後 diff で判断表と接続点の残存・実行手順の参照化を確認する（example-test）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票。起票時前提の補正1件 — 2→3マニフェスト — を説明欄に明記。縮退維持・minor bump の人間裁定 2026-07-13 を反映）
  - 1.0 (2026-07-18) EARS 行の折返しを解消（spec_inspect lint 対応。文言・内容の変更なし）
