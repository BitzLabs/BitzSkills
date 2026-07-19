---
id: ENV-FR-011
version: 1.0
status: approved
domain: deploy
priority: medium
origin: SI-CORE-032
verification_method: manual-check
derived_from: CORE-CON-009
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-011 env-update バージョン更新とマイグレーション機構

- **説明**: env-init で展開済みの環境（settings.json の permissions・AGENTS.md / CLAUDE.md の
  マーカー区間・`.claude/agents/` の advisor / worker・`.claude/bitz-env.local.md` レジストリ）を
  ライブラリ側の最新バージョンへ安全に更新する標準ライフサイクルスキル `env-update` を提供する。
  CORE-CON-008 の update 最小契約（バージョン更新と依存再確認）と CORE-CON-009 の
  累積マイグレーション機構（任意拡張）に準拠する（DSN-003 / DSN-002 に基づく）。
- **受入基準 (EARS)**:
  - WHEN env-update を実行する THEN レジストリ（`.claude/bitz-env.local.md`）に記録された展開時バージョン D とライブラリ側バージョン T を比較し、差分のある生成物のみを更新すること SHALL
  - WHEN 生成物を更新する THEN env-init が管理するマーカー区間の外側（ユーザー編集領域）を変更しないこと SHALL
  - THE env-update は CORE-CON-009 のマイグレーション機構（適用候補 D < to <= T の to 昇順チェーン解決・連続性検査・from 昇順の逐次適用）に準拠すること SHALL
  - WHEN `references/migrations/` にステップが存在しない THEN 形式変更なしとして生成物の差分更新のみを行うこと SHALL（初回出荷時は migrations/ 空を正とする）
  - WHEN 同一マイグレーションステップが同一状態に二重適用される THEN guard 条件により no-op となり状態が壊れないこと SHALL
  - IF D または T が semver として解釈不能、またはチェーンに断裂・欠落がある THEN 書き込み前に安全側停止し、状態と不足をユーザーへ提示すること SHALL
  - WHEN 書き込み先がリポジトリ外である THEN dry-run の差分提示とユーザー承認の取得後にのみ書き込むこと SHALL
  - WHEN 更新を完了する THEN レジストリの記録バージョンを T へ更新し、依存の再確認結果を報告すること SHALL
- **検証手段**: plugin-creator `migration-steps.md` 記載の合成フィクスチャ手順で
  「チェーン断裂時の安全側停止」「同一ステップ二重適用の no-op」を確認（`evals/` に記録）+
  skill-validator チェックリスト通過 + release_check / spec_inspect PASS。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（draft 起票。SI-CORE-032 / DSN-003 / DSN-002 由来）
