---
implements: SDD-FR-120
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-plan/
status: done
---

### sdd-plan スキル新設（現状把握と次アクション提案）

- **作業内容**: `plugins/bitz-sdd/skills/sdd-plan/SKILL.md` を新設する。動作は sdd-core 同梱の
  spec_status.py の実行と結果解釈に限定した薄い判断層とする:
  ①spec_status.py 実行（機械集計）→②フェーズ判定とゲート状態（sdd-core の gates.md をスキル名言及で参照）→
  ③次アクション提案（着手可能タスク・裁定待ち spec-issue・draft 要件の一覧・blocked の理由）。
  スキル本文に集計ロジックを書かない。原則ファイルを書かない（STATE.md 更新は spec_update.py 経由のみ）。
  sdd-report との責務境界（レポート成果物 vs 対話ナビゲーション）を SKILL.md に明記する。
  description は sdd-report のトリガー（「進捗を教えて」「レポート」）と衝突しないよう
  「次何をすべき」「現状把握」系に限定する。frontmatter は metadata（version/author/created/updated）必須。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
