---
id: ENV-FR-004
version: 1.1
status: verified
domain: deploy
priority: medium
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-004 マーカー区間による再生成

- **説明**: bitz-env が CLAUDE.md / AGENTS.md へ挿入する内容はマーカーコメント
  `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->` で囲み、再実行・更新時は
  その区間だけを再生成しなければならない。区間外の既存記述の変更は禁止する。
- **受入基準 (EARS)**:
  - WHEN env-init / env-register が CLAUDE.md・AGENTS.md を更新する THEN システムは マーカー区間の内側のみを書き換える SHALL
  - WHEN 既存ファイルへマーカー区間を追記する THEN システムは 区切りに必要な空白・改行をマーカー開始タグの内側（`<!-- bitz-env:begin -->` の直後）に含め、マーカー区間外へ新規バイトを一切追加しない SHALL
  - IF 対象ファイルにマーカー区間が存在しない（env-register 実行時）THEN システムは 先に env-init の実行を案内し、勝手に区間を新設しない SHALL
- **検証手段**: evals/env-init/・evals/env-register/（区間外不変のアサーション）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.0 (2026-07-11) implementing 遷移（実装タスク done 確認・sdd-test 工程開始）
  - 1.1 (2026-07-12) SI-ENV-008 裁定反映: 区切り空白・改行はマーカー開始タグの内側に含め、区間外へ新規バイトを追加しない受入基準を追加（evals/env-init TC-02 の実測に基づく）
  - 1.1 (2026-07-12) verified 遷移（evals/env-init TC-02 再テスト runs/10 green（v1.1 基準）・env-register TC-04 green + spec_inspect PASS、人間承認）
