---
id: CORE-FR-003
version: 1.1
status: verified
domain: tooling
priority: medium
origin: SI-CORE-011（プロジェクト改修計画 2026-07-12 ユーザー要望3）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-003 spec_status.py による軽量状況照会

- **説明**: sdd-core に読み取り専用のスクリプト `spec_status.py` を追加し、`.spec/` 配下を
  エージェントが読み歩く代わりに1コマンドで「現在フェーズ・要件/spec-issue/タスクの status 別件数・
  次アクション候補」を取得できるようにする。人間向けテキストとエージェント向け JSON の両方を出力する。
  `sdd_report.py`（人間向け詳細レポートを `.spec/reports/` に生成）とは責務を分け、
  `spec_status.py` は軽量な即時照会に徹し、レポートファイルを生成しない。
- **受入基準 (EARS)**:
  - WHEN `spec_status.py <workspace>` を実行する THEN 要件・spec-issue・タスクを走査し status 別の件数集計を出力すること SHALL
  - WHEN `--json` を指定して実行する THEN 集計・フェーズ・次アクション候補を含む機械可読な JSON を標準出力へ出すこと SHALL
  - WHEN `--json` を指定せず実行する THEN 人間向けテキストサマリを出力すること SHALL
  - THEN `spec_status.py` は実行を通じて `.spec/` 配下へ一切書き込みを行わないこと SHALL（読み取り専用）
  - WHERE 複数ワークスペースを対象とする THEN `--workspace` で複数ルートを受け付けワークスペースごとに集計すること SHALL
  - WHEN いずれの status にも該当しない状況（要件が0件など）THEN エラーを送出せず空集計として妥当に出力すること SHALL
- **検証手段**: tests/test_spec_status.py（fixture の .spec ツリーに対する集計・フェーズ判定・
  JSON 構造・読み取り専用性の回帰テスト、`.venv/bin/pytest` green）
- **Revision History**:
  - 0.1 (2026-07-13) draft 起票（SI-CORE-011 の要件化。approved 化は人間裁定待ち）
  - 1.0 (2026-07-13) approved（人間裁定はチャット指示「OKです」）
  - 1.1 (2026-07-13) verified（tests/test_spec_status.py 14件 green + 実リポジトリ全ワークスペース実行確認により example-test 合格）
</content>
</invoke>
