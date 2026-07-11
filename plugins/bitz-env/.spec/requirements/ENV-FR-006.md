---
id: ENV-FR-006
version: 1.1
status: implementing
domain: collab
priority: medium
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-006 協調アダプタの契約チェックと登録・役割ルーティング

- **説明**: env-register スキルは、協調アダプタ候補が契約（collab-contract.md v2:
  役割スキルの保持 + 能力宣言 collab.agent）に準拠することを確認したうえで
  レジストリ `.claude/bitz-env.local.md` へ登録し、非準拠のプラグインは理由を報告して
  登録してはならない。複数アダプタの共存を前提とし、レジストリには
  「標準の役割（delegate / review / status）→ 当該アダプタの実際のスキル名」の
  ルーティングテーブルを記録する。env-orchestration の委譲先解決はレジストリ経由で行い、
  固定スキル名に依存しない。
- **受入基準 (EARS)**:
  - WHEN アダプタ候補が契約に準拠している THEN システムはユーザー確認のうえ レジストリへ登録し、役割→実スキル名のルーティングテーブルを記録し、CLAUDE.md 委譲マトリクスのアダプタ行を更新する SHALL
  - IF 候補が delegate 相当の役割スキルまたは能力宣言を欠く THEN システムは非準拠の理由を 報告し、登録しない SHALL
  - WHEN 登録時に既登録アダプタとスキル名が衝突する THEN システムは衝突を報告し、レジストリ上で名前空間（アダプタ名によるプレフィックス）と優先順を明示して解決する SHALL
  - WHEN env-orchestration が委譲先を解決する THEN システムはレジストリのルーティングテーブルを参照し、固定スキル名を直接呼ばない SHALL
  - WHEN 登録済みアダプタがアンインストールされている THEN システムはユーザー確認の うえレジストリのエントリを削除する SHALL
- **検証手段**: evals/env-register/（準拠/非準拠/名前衝突/棚卸しシナリオ）・evals/env-orchestration/（レジストリ経由の解決）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.1 (2026-07-11) SI-ENV-005 accepted による改訂: 役割ルーティングテーブル・名前衝突解決を追加、契約 v2 前提
  - 1.1 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.1 (2026-07-11) implementing 遷移（実装タスク done 確認・sdd-test 工程開始）
