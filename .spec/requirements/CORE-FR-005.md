---
id: CORE-FR-005
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-012（プロジェクト改修計画 2026-07-12 ユーザー要望3。定型処理のスクリプト化）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-005 spec_update.py による status 遷移の権限強制と STATE.md 更新

- **説明**: 要件 / spec-issue / タスクの status 遷移を行うスクリプト `spec_update.py` を提供し、
  sdd-core の権限マトリクス（references/lifecycle.md）をコードで強制する。
  エージェントが実行できる遷移と人間専用の遷移を分け、人間専用遷移は `--by-human` フラグの
  明示がない限り拒否する。これにより権限逸脱（エージェントによる無断の approved 化等）を
  構造的に防ぐ。
- **受入基準 (EARS)**:
  - WHEN 人間専用遷移（draft→approved / open→accepted / verified→promoted / 任意→deprecated）を `--by-human` なしで要求する THEN 当該遷移を拒否し非ゼロで終了すること SHALL
  - WHEN `--by-human` を明示し権限マトリクス上で許可された人間専用遷移を要求する THEN 当該遷移を適用すること SHALL
  - WHEN エージェント許容遷移（起票→open / approved→implementing / implementing→verified 等）を要求する THEN `--by-human` なしでも当該遷移を適用すること SHALL
  - IF 要求された遷移が権限マトリクスに定義されていない（不正遷移） THEN 誰の権限であっても拒否し非ゼロで終了すること SHALL
  - WHEN status 遷移を適用する THEN 対象ファイルの frontmatter `status` を更新し `.spec/STATE.md` に遷移記録（対象 ID・旧→新 status・実行主体）を追記すること SHALL
- **検証手段**: tests/test_spec_update.py（テスト先行）。`--by-human` なしでの approved 化拒否、
  `--by-human` ありでの許可、エージェント許容遷移の適用、不正遷移の拒否、STATE.md 追記を
  example-test で検証する。
- **Revision History**:
  - 1.0 (2026-07-13) 初版（SI-CORE-012 の要件化ドラフト。テスト先行）
  - 1.0 (2026-07-13) 人間裁定により approved 化（チャット指示）
