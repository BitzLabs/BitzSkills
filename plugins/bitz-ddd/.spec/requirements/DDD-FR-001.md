---
id: DDD-FR-001
version: 1.0
status: approved
domain: tooling
priority: medium
origin: SI-CORE-031
verification_method: manual-check
derived_from: CORE-CON-008
supersedes:
superseded_by:
confidence: high
---

### DDD-FR-001 ddd-doctor 環境診断スキルと依存宣言

- **説明**: bitz-ddd は bitz-sdd との併用が前提（全スキルの description に明記）だが、
  マニフェストに依存宣言が無く、欠如を機械検出できない。CORE-FR-013 書式の依存宣言を
  追加し、標準ライフサイクルスキル `ddd-doctor` がその充足を読み取り専用で診断する
  （CORE-CON-008 の doctor 最小契約、DSN-003 のマトリクスに基づく）。
- **受入基準 (EARS)**:
  - THE bitz-ddd は3マニフェスト（`.claude-plugin/plugin.json` / `plugin.json` / `.codex-plugin/plugin.json`）の `metadata.dependencies` に bitz-sdd への依存を semver 制約つきで宣言すること SHALL（CORE-FR-013 書式）
  - THE ddd-doctor は読み取り専用で診断を行い、対象プロジェクト・配置先への書き込みを一切行わないこと SHALL
  - WHEN 診断を実行する THEN 依存プラグイン bitz-sdd の有効性と semver 制約の充足を診断し、欠如・制約不満足の場合は導入手順つきの修正案を報告すること SHALL
  - WHEN 利用プロジェクトに `.spec/design/` が存在する THEN bitz-ddd 成果物（domain-model.md / stories/）の配置前提（.spec/ ワークスペースの存在）を診断に含めること SHALL
  - IF すべての診断項目に問題がない THEN OK 判定と各項目の根拠を簡潔に報告すること SHALL
- **検証手段**: skill-validator チェックリスト通過 + 3マニフェストの依存宣言を
  release_check（依存グラフ検査）で機械確認 + SKILL.md の目視確認。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（draft 起票。SI-CORE-031 / DSN-003 由来）
