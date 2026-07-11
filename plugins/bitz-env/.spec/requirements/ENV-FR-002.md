---
id: ENV-FR-002
version: 1.0
status: draft
domain: guardrail
priority: high
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-002 フック入力のプラットフォーム自動判別と安全な失敗

- **説明**: env_guard.py は stdin の JSON 形状からプラットフォームを自動判別し
  （toolCall キー → Antigravity / tool_name・tool_input キー → Claude Code）、
  判別不能・不正な入力に対しては介入せず安全に素通ししなければならない。
- **受入基準 (EARS)**:
  - WHEN stdin に toolCall キーを含む JSON が渡される THEN システムは Antigravity の 契約（decision）で応答する SHALL
  - WHEN stdin に tool_name または tool_input キーを含む JSON が渡される THEN システムは Claude Code の契約（hookSpecificOutput.permissionDecision）で応答する SHALL
  - IF stdin が JSON としてパースできない THEN システムは空応答 `{}` を返し 正常終了する SHALL（ガードの故障がツール実行全体を止めない）
- **検証手段**: tests/test_env_guard.py（形状判別・不正入力・unknown 形状）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
