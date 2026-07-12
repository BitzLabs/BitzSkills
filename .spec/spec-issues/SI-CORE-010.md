---
id: SI-CORE-010
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 1。docs/improvement_master_plan.md）
target: plugins/bitz-sdd/skills/sdd-git（bitz-flow との二重規定の解消）
proposed_change_type: bump
status: open
---
- **目的**: SI-CORE-008/009 で bitz-flow が実用可能になった後、bitz-sdd 側の sdd-git を
  bitz-flow への委譲に切り替え、Git フローの正を bitz-flow に一本化する（動作変更のみ）。
- **提案する修正**:
  1. sdd-git を薄い委譲ポインタに縮退する（フロー選択の判断表と SDD 固有の接続点
     —Implements フッター・タスク並列投入条件—だけ残し、実行手順は bitz-flow を参照）。
     完全廃止（major bump）か縮退維持（minor bump）かは人間裁定
  2. bitz-sdd のマニフェストに `metadata.dependencies: ["bitz-flow"]` を宣言する
     （SI-CORE-007 の機構を利用）
  3. sdd-core の parallel-git.md・sdd-implement 等からの sdd-git 参照を確認し、
     参照先の記述を更新する（規定の正の所在を1箇所に保つ）
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-git/**`、`plugins/bitz-sdd/.claude-plugin/plugin.json`
  と `plugin.json`（依存宣言 + bump）、参照箇所（`grep -rn "sdd-git" plugins/ .spec/ docs/` で洗い出し）。
- **確認観点**:
  - release_check PASS（依存グラフ検証を含む）
  - sdd-git への参照の更新漏れがないこと（grep 結果ゼロ or 意図した残置のみ）
  - bitz-sdd 単体インストール時に依存欠如が doctor / release_check で検出できること
- **影響推定・ロールバック**: bitz-sdd の版を1つ戻し bitz-flow を残せば旧構成に戻る。
  SI-CORE-008/009 より後に revert しないこと（依存の向きが逆転するため）。
- **依存**: SI-CORE-007（依存宣言機構）、SI-CORE-009（bitz-flow の実用性）。
