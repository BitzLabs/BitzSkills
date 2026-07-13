---
id: SI-CORE-011
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 3。docs/improvement_master_plan.md）
target: plugins/bitz-sdd/skills/sdd-core/scripts/（状況確認の定型処理が未スクリプト化）
proposed_change_type: bump
status: accepted
requirement: CORE-FR-003
---
- **目的**: 「いま何フェーズか・要件/issue/タスクが何件どの status か・次に何をすべきか」の
  状況確認を、エージェントが .spec/ 配下を読み歩く代わりに1コマンドで得られるようにし、
  セッション冒頭の読み込みトークンを削減する。
- **提案する修正**（**テスト先行**）:
  1. `spec_status.py` を sdd-core/scripts/ に追加する。**読み取り専用**で、
     要件/issue/タスクの status 集計、フェーズ判定、次アクション候補を
     テキスト（人間向け）と JSON（エージェント向け）で出力する。
     `--workspace` 対応（spec_inspect.py と同じ流儀）
  2. sdd-core / sdd-report の SKILL.md に使い分けを明記する
     （sdd_report.py=人間向け詳細レポート生成、spec_status.py=軽量即時照会。重複実装しない）
- **対象ファイル**: `tests/`（先行）、`plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py`、
  sdd-core / sdd-report の SKILL.md（参照追記）、bitz-sdd マニフェスト bump。
- **確認観点**:
  - テスト先行（fixture の .spec ツリーに対する集計・フェーズ判定の回帰テスト）で
    `.venv/bin/pytest` green
  - `.spec/` への書き込みが一切ないこと（読み取り専用の保証）
  - 本リポジトリのルート + 全ワークスペースで実行して妥当な出力が得られること
- **影響推定・ロールバック**: 追加のみ。スクリプトとテストの削除で戻る。
- **依存**: なし（bitz-flow 系と並行可）。
