---
id: ENV-FR-008
version: 1.0
status: implementing
domain: guardrail
priority: medium
origin: 人間裁定（チャット指示 2026-07-11。要検証項目#2 の設計解決）
verification_method: example-test
derived_from: ENV-DSN-001
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-008 rules/*.md の両プラットフォーム読み込み

- **説明**: プラグイン同梱のルール文書（rules/*.md）は、両プラットフォームで
  セッションのコンテキストに読み込まれなければならない。Antigravity はネイティブの
  rules コンポーネント、Claude Code は SessionStart フック（stdout がコンテキストへ
  自動追加される公式仕様）による注入で実現する。
- **受入基準 (EARS)**:
  - WHEN Claude Code のセッションが開始される THEN システムは SessionStart フックで rules/*.md の内容を stdout へ出力しコンテキストに注入する SHALL
  - WHEN Antigravity でプラグインが有効である THEN rules/*.md はシステムルールへマージされる SHALL
  - IF rules/ が空または読めない THEN フックはエラーでセッションを妨げない SHALL
- **検証手段**: tests/test_env_guard.py（hooks.json の SessionStart 定義と注入コマンドの
  出力検証）+ 実環境での注入確認
- **Revision History**:
  - 1.0 (2026-07-11) 初版。人間裁定により approved で起票（チャット指示。
    根拠: code.claude.com/docs hooks-guide「stdout is added to Claude's context」。
    プラグインの rules/ ネイティブ対応は Claude Code に無いことを公式 docs で確認済み）
  - 1.0 (2026-07-11) implementing 遷移（実装タスク done 確認・sdd-test 工程開始）
