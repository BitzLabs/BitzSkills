---
id: ENV-CON-003
version: 1.0
status: draft
domain: deploy
priority: high
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: inspection
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-CON-003 生成・記録は対象プロジェクト内に限定

- **説明**: bitz-env のスキル（env-init / env-register / env-doctor）が書き出す
  生成物・レジストリ・診断結果は、対象プロジェクトのリポジトリ内に限定する。
  ホームディレクトリ等プロジェクト外への書き込みを行ってはならない。
- **受入基準 (EARS)**:
  - WHEN スキルがファイルを書き出す THEN 書き出し先は対象プロジェクトの ルート配下である SHALL
  - IF プロジェクト外への書き込みが必要に見える状況 THEN システムは実行せず ユーザーに理由を確認する SHALL
- **検証手段**: evals/ のシナリオテスト（書き出し先パスのアサーション）+ コードレビュー
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
