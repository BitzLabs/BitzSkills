---
id: ENV-FR-001
version: 1.0
status: verified
domain: guardrail
priority: high
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-001 同梱フックによる破壊的操作の deny

- **説明**: プラグイン同梱の PreToolUse フック（env_guard.py）は、破壊的操作5種
  （rm -rf、git push --force/-f、git reset --hard、git clean -f、sudo）を検出した場合、
  実行を deny しなければならない。
- **受入基準 (EARS)**:
  - WHEN ツール実行の引数が破壊的操作5種のいずれかに一致する THEN システムは プラットフォームの契約に従い deny 応答（Claude Code: permissionDecision=deny / Antigravity: decision=deny）を返す SHALL
  - WHEN 引数がいずれのパターンにも一致しない THEN システムは空応答 `{}` を返し 実行に介入しない SHALL
- **検証手段**: tests/test_env_guard.py（deny 5種 × 両プラットフォーム、pass ケース）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.0 (2026-07-11) implementing 遷移（実装タスク done 確認・sdd-test 工程開始）
  - 1.0 (2026-07-11) verified 遷移（pytest 全 green + spec_inspect PASS、人間承認）
