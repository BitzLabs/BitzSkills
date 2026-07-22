---
id: SI-CORE-016
raised_by: プロジェクト改修計画 追加要望（2026-07-12 ユーザー提案: sdd-plan 新設）
target: plugins/bitz-sdd/skills/sdd-plan（新設。spec 現状把握と次アクション提案）
proposed_change_type: new
status: accepted
delegated_to: bitz-sdd:SDD-FR-120
---
- **目的**: 「いまどこまで進んでいて、次に何をすべきか」を対話で答えるナビゲーション
  スキル sdd-plan を新設する。現状この役割は sdd-core のフェーズ・ルーティング表を
  エージェントが都度読んで解釈しており、専用トリガー（「次何をすべき」「現状把握」）が無い。
- **提案する修正**:
  1. `plugins/bitz-sdd/skills/sdd-plan/` を新設する。動作は
     **spec_status.py（SI-CORE-011）の実行と結果解釈に限定した薄い判断層**とする:
     ①spec_status.py 実行（機械集計）→ ②フェーズ判定とゲート状態（gates.md 参照）→
     ③次アクション提案（着手可能タスク、裁定待ち SI・draft 要件の一覧、blocked の理由）
  2. 責務境界を明記する: sdd-report は人間向け成果文書の生成（.spec/reports/ に書く）、
     sdd-plan はセッション内の対話ナビゲーション（原則ファイルを書かない。
     STATE.md 更新は spec_update.py 経由のみ）。二重実装を作らない
  3. sdd-core のフェーズ・ルーティング表に sdd-plan の行を追加し、
     「現状把握・次アクション」のルーティング先を sdd-plan に一本化する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-plan/SKILL.md`（新規）、
  sdd-core / sdd-report の SKILL.md（責務境界とルーティングの追記）、bitz-sdd マニフェスト bump。
- **確認観点**:
  - スキル本文に集計ロジックを書いていないこと（決定的処理はすべて spec_status.py 側）
  - description のトリガーが sdd-report（「進捗を教えて」「レポート」）と衝突しないこと
    （skill-tester で発動テスト）
  - skill-validator / release_check PASS
- **影響推定・ロールバック**: スキル追加と参照追記のみ。フォルダ削除 + 追記 revert で戻る。
- **依存**: SI-CORE-011（spec_status.py が実体。本スキルはその判断層）。
- **実施**: bitz-sdd ワークスペースの SDD-FR-120（sdd-plan スキル新設）へ委譲・要件化し実装。
  PR #45 でマージ、SDD-FR-120 verified 済み（クロス WS 委譲。`delegated_to: bitz-sdd:SDD-FR-120`）。
