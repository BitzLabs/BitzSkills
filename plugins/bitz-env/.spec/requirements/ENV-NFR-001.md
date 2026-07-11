---
id: ENV-NFR-001
version: 1.0
status: approved
domain: guardrail
priority: medium
origin: SI-ENV-004（REV-001 business BIZ-201）
verification_method: benchmark
derived_from:
supersedes:
superseded_by:
confidence: medium
---

### ENV-NFR-001 ガードの応答時間

- **説明**: env_guard.py は全 Bash 実行に PreToolUse で割り込むため、応答が遅いと
  開発体験を直接損なう。通常環境で体感を損なわない応答時間に収める。
- **受入基準 (EARS)**:
  - WHEN env_guard.py が1回のフック呼び出しを処理する THEN システムは通常環境で 200ms 以内に応答を返す SHALL
- **検証手段**: tests/ での実行時間計測（benchmark。代表入力での経過時間アサーション）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（SI-ENV-004 accepted による）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
