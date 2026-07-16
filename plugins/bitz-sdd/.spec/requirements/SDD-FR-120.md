---
id: SDD-FR-120
version: 1.0
status: verified
domain: workflow
priority: medium
origin: SI-CORE-016（ルート .spec/spec-issues/。2026-07-12 ユーザー提案: sdd-plan 新設）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-120 sdd-plan スキルによる現状把握と次アクション提案

- **説明**: 「いまどこまで進んでいて、次に何をすべきか」を対話で答えるナビゲーションスキル sdd-plan を新設する。現状この役割は sdd-core のフェーズ・ルーティング表をエージェントが都度読んで解釈しており、専用トリガー（「次何をすべき」「現状把握」）が無い。sdd-plan は spec_status.py（機械集計）の実行と結果解釈に限定した薄い判断層とし、sdd-report（人間向け成果文書を .spec/reports/ に生成）との二重実装を作らない。
- **受入基準 (EARS)**:
  - WHEN ユーザーが「次に何をすべきか」「現状把握」等でナビゲーションを求めたとき THEN sdd-plan は spec_status.py を実行し、①フェーズ判定とゲート状態（gates.md 参照）②次アクション提案（着手可能タスク・裁定待ち spec-issue・draft 要件の一覧・blocked の理由）を対話で提示する SHALL
  - WHERE 集計・カウント等の決定的処理が必要な場合 THE sdd-plan は自前の集計ロジックを持たず spec_status.py の出力のみを解釈する SHALL
  - WHILE セッション内の対話ナビゲーションを行っている間 THE sdd-plan は原則ファイルを書かない（STATE.md 更新が必要な場合も spec_update.py 経由のみとする） SHALL
  - WHEN sdd-core のフェーズ・ルーティング表が「現状把握・次アクション」の行を案内するとき THEN ルーティング先は sdd-plan に一本化されている SHALL
- **検証手段**: skill-validator チェックリスト PASS + release_check PASS + skill-tester による発動テスト（description が sdd-report のトリガー「進捗を教えて」「レポート」と衝突しないこと）+ SKILL.md の目視確認（集計ロジック不在・ファイル非生成の原則・sdd-report との責務境界の明記）
- **Revision History**:
  - 1.0 (2026-07-16) 初版（draft 起票）
