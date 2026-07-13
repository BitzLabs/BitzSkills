---
implements: CORE-FR-003
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py
status: done
---

### spec_status.py 追加（軽量状況照会・読み取り専用）

- **作業内容**: sdd-core に読み取り専用スクリプト `spec_status.py` を追加し、要件/spec-issue/タスクの
  status 別件数集計・フェーズ判定・次アクション候補をテキスト+JSON で出力する（`--workspace` 対応）。
  テスト先行で `tests/test_spec_status.py` を作成。sdd-core / sdd-report の SKILL.md に
  `sdd_report.py` との使い分けを明記。
- **実施記録**: 2026-07-13 実施。`.venv/bin/pytest tests/test_spec_status.py` 14件 green、
  実リポジトリのルート + 全ワークスペースで妥当な出力を確認。sdd-core 1.8.0 / sdd-report 0.2.4 /
  bitz-sdd を bump。
- **備考**: 軽量レーン適用（spec-issue SI-CORE-011 → 要件 CORE-FR-003 → タスクのみ。discovery / design スキップ）。
  読み取り専用（`.spec/` へ書き込まないこと）を回帰テストで担保。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
