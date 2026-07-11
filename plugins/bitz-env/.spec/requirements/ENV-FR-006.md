---
id: ENV-FR-006
version: 1.0
status: draft
domain: collab
priority: medium
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-006 協調アダプタの契約チェックと登録

- **説明**: env-register スキルは、協調アダプタ候補が契約（collab-contract.md v1:
  delegate スキルの保持 + 能力宣言 collab.agent）に準拠することを確認したうえで
  レジストリ `.claude/bitz-env.local.md` へ登録し、非準拠のプラグインは理由を報告して
  登録してはならない。
- **受入基準 (EARS)**:
  - WHEN アダプタ候補が契約に準拠している THEN システムはユーザー確認のうえ レジストリへ登録し、CLAUDE.md 委譲マトリクスのアダプタ行を更新する SHALL
  - IF 候補が delegate スキルまたは能力宣言を欠く THEN システムは非準拠の理由を 報告し、登録しない SHALL
  - WHEN 登録済みアダプタがアンインストールされている THEN システムはユーザー確認の うえレジストリのエントリを削除する SHALL
- **検証手段**: evals/env-register/（準拠/非準拠/棚卸しシナリオ）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
