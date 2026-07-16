---
id: SDD-FR-112
version: 1.0
status: verified
domain: execution
priority: medium
origin: SI-SDD-004（2026-07-14 SI-CORE-021 開発の振り返り。部分検収でマージ後 CI 回帰）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-112 共有スクリプト変更時の全テストスイート実行と環境固有前提のスキップ扱い

- **説明**: 実装タスクの検収を「対象テストのみの部分実行」で済ませると、共有スクリプト（`scripts/` 配下やプラグイン同梱スクリプト等、広く参照される契約）の変更で他 fixture の回帰を見逃す。これを防ぐため、sdd-implement / sdd-test は共有スクリプトに触れるタスクの検収に全テストスイート実行を必須とし、かつ検査が特定ファイルの実在に依存する場合の不在を「違反」ではなく「スキップ」として扱う指針を明示しなければならない。
- **受入基準 (EARS)**:
  - WHEN 共有スクリプト（`scripts/` 配下・プラグイン同梱スクリプト・広く参照される契約）に触れるタスクを done にしようとするとき THEN sdd-implement / sdd-test は対象テストのみの部分実行で完了とせず、全テストスイートの実行を必須とする SHALL
  - WHERE 検査が特定ファイル（例: CLAUDE.md）の実在を前提とする場合 THE system は当該ファイルの不在を検査違反ではなくスキップとして扱う SHALL
- **検証手段**: `implementation-discipline.md` と `sdd-test/SKILL.md` の目視確認（「共有スクリプト変更時は全スイート実行」と「環境固有前提の不在＝スキップ」が検収規律として明記されていること）+ skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-16) 初版（draft 起票）
