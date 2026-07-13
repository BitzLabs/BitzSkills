---
id: SI-CORE-021
raised_by: 2026-07-13 セッションの振り返り（Opus が全作業を直接実行し委譲・省トークンゼロ）
target: sdd-core/sdd-implement の Execute フェーズ × bitz-env env-orchestration × CLAUDE.md 委譲マトリクスの未連結
proposed_change_type: new
status: open
---
- **目的**: SDD の Execute（実装）フェーズに**委譲の判定・実行を促す機構がない**ため、
  司令塔（Fable 5／不在時は Opus）が機械的作業まで直接実行してトークンを浪費する構造を是正する。
  委譲マトリクス（CLAUDE.md）と bitz-env の協調運用（env-orchestration）を SDD 実装フローに連結する。
- **背景（実事例）**: 2026-07-13 セッション（SI-CORE-012 実装ほか）で、要件設計・テスト先行4ファイル・
  スクリプト2本・frontmatter 更新・pytest 実行・status 遷移まで**すべて Opus が直接実行**し、
  `env-orchestration`・委譲先サブエージェント（deep-reasoner/fast-worker）・antigravity を**一度も使わなかった**。
  結果、下位モデルによる省トークンはゼロ。CLAUDE.md「実作業は委譲してトークンを温存する」に反した。
- **根本原因（調査で裏付け済み）**:
  1. 委譲規律は CLAUDE.md にナラティブで在るのみで、**Execute 入口で委譲を促す機構がない**。
  2. `sdd-implement/SKILL.md` は並列投入を `depends_on`/`boundary` で判定するだけで、
     **委譲マトリクスを一切参照していない**。
  3. `env-orchestration` は能動起動型の案内スキルで、SDD 実装フェーズから誘導されない。
  4. 「Fable 5 不在時は Opus を司令塔として同運用継続」の規定が、実行時に「Opus＝作業者」と取り違えられた。
- **提案する修正（人間が取捨選択。主提案 = 1）**:
  1. **【主提案】委譲ゲートの新設**: `sdd-implement` に「タスク着手前の委譲判定」ステップを追加する。
     各タスクを委譲マトリクスで分類（機械的→fast-worker / 設計・難調査→deep-reasoner / 量産→antigravity）し、
     損益分岐を超えるものは司令塔が直接書かず委譲する。手順は短い reference（例: `references/delegation-routing.md`）に切り出す。
  2. **Execute 入口での env-orchestration surfacing**: `sdd-implement`（または sdd-core のフェーズ・ルーティング表）から
     `env-orchestration` を明示クロス参照し、実装移行時に決定木（委譲型/相談型/合議型）が想起されるようにする。
  3. **司令塔フォールバックの明確化**: CLAUDE.md／env-orchestration に「Opus が司令塔でも機械的作業は
     Sonnet fast-worker へ委譲。司令塔は作業者にならない」を1行強調で追記する。
  4. **（任意）計測**: Execute フェーズごとに委譲有無を `.spec/metrics.md` に記録し、不作為を振り返りで可視化する。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-implement/SKILL.md`（+ 新規 `references/delegation-routing.md`）、
  `plugins/bitz-sdd/skills/sdd-core/SKILL.md`（ルーティング表）、`plugins/bitz-env/skills/env-orchestration/SKILL.md`、
  ルート `CLAUDE.md`、必要なら bitz-sdd / bitz-env マニフェスト bump。
- **確認観点**:
  - ドキュメント／規約の追加であって既存挙動を変えないこと（規定の追加であって変更でない）
  - release_check / spec_inspect PASS
  - 提案が「主提案（委譲ゲート）」と「補助提案」を分けて記述されていること
  - 委譲の損益分岐（小さな単発は委譲しない）を明記し、過剰委譲を誘発しないこと
- **影響推定・ロールバック**: ナラティブ文書・規約への追加が中心。設計分岐（どこに機構を置くか）は人間裁定。
  実装は後続 PR で通常フロー相当（複数スキル横断のため軽量レーン非適用）。単独 revert 可能。
- **依存**: なし（013/006 の実装とは独立。裁定・実装は本 ISSUE とは別 PR）。
