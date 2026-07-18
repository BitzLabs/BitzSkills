---
id: ENV-FR-010
version: 1.1
status: verified
domain: deploy
priority: high
origin: SI-ENV-006（sdd-review 第2ラウンド クロスモデル AGY-7）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-010 生成物のトラッキングと env-uninstall による撤去

- **説明**: フック（即効層）はプラグイン無効化で消えるが、env-init が生成した恒久層
  （settings.json の permissions・AGENTS.md / CLAUDE.md のマーカー区間・
  .claude/agents/ の advisor / worker）はアンインストール後も残留する。
  env-init は生成物をレジストリ `.claude/bitz-env.local.md` にトラッキングし、
  env-uninstall スキルがそれを根拠にユーザー確認付きで安全に撤去できなければならない。
  ENV-FR-009（生成前バックアップ）と対を成すライフサイクル管理であり、
  撤去対象はプロジェクト内に限定する（ENV-CON-003 と整合）。
- **受入基準 (EARS)**:
  - WHEN env-init がファイルを生成または既存ファイルへマーカー区間を書き込む THEN システムは生成ファイル一覧とマーカー区間の位置をレジストリに記録する SHALL
  - WHEN env-uninstall を実行する THEN システムはレジストリの記録に基づき撤去対象の一覧を提示し、ユーザー確認を得てから撤去する SHALL
  - WHERE 既存ファイル（settings.json / AGENTS.md / CLAUDE.md）を撤去処理する箇所 THE システムはマーカー区間（bitz-env 生成部分）のみを除去し、ユーザー自身の記述を保持する SHALL
  - IF レジストリが存在しない・記録が欠落している THEN システムは推測で削除せず、検出できた候補を報告してユーザーの個別判断に委ねる SHALL
- **検証手段**: evals/env-destroy/（トラッキング記録・マーカー区間のみ除去・レジストリ欠落時の安全側動作。
  ディレクトリ名はスキル改名前の evals 成果物のため据え置き — evals/ 配下の改名はリポジトリガードレール上
  事前確認が必要な操作のため本タスクでは行わない）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（SI-ENV-006 accepted による）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.0 (2026-07-11) implementing 遷移（実装タスク done 確認・sdd-test 工程開始）
  - 1.0 (2026-07-12) verified 遷移（evals/env-init TC-01・env-destroy TC-01〜03 green + spec_inspect PASS、人間承認）
  - 1.1 (2026-07-18) CORE-CON-008（標準ライフサイクルスキル名）に追随し、スキル名を
    env-destroy → env-uninstall へ改名（挙動は変更なし。evals/env-destroy/ は
    既存成果物のため改名せず据え置き）
