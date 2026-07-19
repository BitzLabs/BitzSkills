---
id: SDD-FR-130
version: 1.0
status: approved
domain: workflow
priority: medium
origin: SI-CORE-031
verification_method: manual-check
derived_from: CORE-CON-008
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-130 sdd-doctor 環境診断スキル

- **説明**: bitz-sdd を導入したプロジェクト環境の健全性を読み取り専用で診断する
  標準ライフサイクルスキル `sdd-doctor` を提供する（CORE-CON-008 の doctor 最小契約、
  DSN-003 のマトリクスに基づく。SI-CORE-010 の確認観点「単体インストール時の依存欠如が
  doctor で検出できること」を実体化する）。
- **受入基準 (EARS)**:
  - THE sdd-doctor は読み取り専用で診断を行い、対象プロジェクト・配置先への書き込みを一切行わないこと SHALL
  - WHEN 診断を実行する THEN マニフェスト `metadata.dependencies` に宣言された依存プラグイン（bitz-flow>=0.2）の有効性と semver 制約の充足を診断し、欠如・制約不満足の場合は導入手順つきの修正案を報告すること SHALL
  - WHEN 利用プロジェクトに `scripts/spec` ラッパー（SI-CORE-022 方式）が存在する THEN `installed_plugins.json` からの bitz-sdd バージョン非依存解決が成立するかを診断すること SHALL
  - WHEN 利用プロジェクトに `.spec/` ワークスペースが存在する THEN 読み取り専用の `spec_status.py` による状況照会が実行可能かを診断に含めること SHALL（`spec_inspect.py` はレポートを書き込むため doctor からは実行しない）
  - IF すべての診断項目に問題がない THEN OK 判定と各項目の根拠を簡潔に報告すること SHALL
- **検証手段**: skill-validator チェックリスト通過 + SKILL.md の目視確認（読み取り専用の明記・
  診断項目と修正案の記載）+ release_check / spec_inspect PASS。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（draft 起票。SI-CORE-031 / DSN-003 由来）
