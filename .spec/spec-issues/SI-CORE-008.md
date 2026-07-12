---
id: SI-CORE-008
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 1。docs/improvement_master_plan.md）
target: plugins/bitz-flow（新設）と .claude-plugin/marketplace.json
proposed_change_type: new
status: open
---
- **目的**: Git / GitHub 開発フローを SDD 非採用プロジェクトでも使える独立プラグイン
  bitz-flow として切り出す。本 ISSUE は**構造の新設のみ**（sdd-git の内容転記）で、
  既存 bitz-sdd の挙動は一切変えない（挙動変更は SI-CORE-010 に分離）。
- **提案する修正**:
  1. AGENTS.md の「新しいプラグインの追加手順」に従い `plugins/bitz-flow/` を新設
     （2マニフェスト + marketplace.json 登録）
  2. sdd-git の内容を汎用化して転記する。スキル構成案:
     `flow-core`（フロー選択・コミット規約）/ `flow-worktree`（worktree 運用）/
     `flow-pr`（GitHub Issue 駆動 + Draft PR + squash merge）。
     SDD 固有部分（Implements フッター、.spec/tasks 連携）は「bitz-sdd 併用時」節に隔離する
  3. 新設と同時に `plugins/bitz-flow/.spec/` を作成し sdd-discovery を実施する
     （プレフィックス `FLW-`。SI-CORE-005 と同じ書式）
  4. この時点では sdd-git は無変更のまま併存させる（二重規定は SI-CORE-010 で解消）
- **対象ファイル**: `plugins/bitz-flow/**`（新規）、`.claude-plugin/marketplace.json`（1エントリ追加）。
- **確認観点**:
  - release_check PASS（マニフェスト2つの version 一致、marketplace 整合、frontmatter 必須項目）
  - plugin-validator エージェントによる構造検証 PASS
  - 既存プラグインの diff がゼロであること（marketplace.json を除く）
- **影響推定・ロールバック**: フォルダと marketplace エントリの削除で完全に戻せる。
- **依存**: SI-CORE-006（スキル命名は共通ライフサイクル標準に従うため）。
