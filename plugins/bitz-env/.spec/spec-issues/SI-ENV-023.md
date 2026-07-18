---
id: SI-ENV-023
raised_by: CORE-DSC-001 BitzLabs標準環境の3プラットフォーム適合性確認
target: bitz-env の OpenAI Codex 向けガードレール・env-init対応
proposed_change_type: new
status: open
---
- **目的**: bitz-env は `.codex-plugin/plugin.json` を持ちCodex CLIへインストールできるが、
  現行の機械フック契約・rules注入・`env-init` のプラットフォーム選択は
  Claude Code / Antigravity 2.0 の2環境だけを対象とする。Codexでは収録スキルとAGENTS.mdの
  ナラティブは利用できる一方、同等の機械ガードを提供していない。CORE-DSC-001で
  「BitzLabs標準環境」を3プラットフォームへ配布する目標を置いたため、機能差を解消するか、
  明示的な劣化モードとして契約化する。
- **提案する修正**:
  1. 現行Codexの公式プラグイン・hooks・sandbox / approval・project config仕様を一次資料とCLI実測で調査する。
  2. Codexネイティブの機械ガードが安全に実装可能なら、既存2環境と同じ禁止操作を満たす
     アダプタ、マニフェスト、example-testを設計する。
  3. 同等実装が不可能または不適切なら、AGENTS.md + Codex sandbox / approvalを使う劣化モードを
     `env-init` / `env-doctor` の正式な3番目の分岐として定義し、検出可能にする。
  4. README・discovery・要件の「両プラットフォーム」とCodexインストール案内を整合させる。
- **対象ファイル**: `plugins/bitz-env/skills/env-init/`、`env-doctor/`、`hooks/` / `rules/`、
  `.codex-plugin/plugin.json`（必要な場合）、bitz-envの `.spec/`・README・テスト、3マニフェストversion。
- **確認観点**:
  - 既存要件との矛盾: ENV-FR-001/002/008は2環境契約としてverified。Codexを追加する場合は
    既存greenを赤にし得るため、要件bumpまたは新要件として扱う。
  - ガードレール: Codexのsandbox / approvalを弱める設定を標準化しない。判別不能時は安全側に停止または
    明示的な非適用報告とする。
  - 検証: 既存Claude/Antigravity example-testを維持し、Codexの実契約をfixtureだけで捏造せず
    CLI実測または公式仕様で裏付ける。
  - 軽量レーン適否: **不適**。フック契約と標準環境の安全境界に触れるため通常フロー + Design Gate。
- **影響推定・ロールバック**: bitz-env全体のガードレール、生成物、診断、配布説明へ影響する。
  新規Codex分岐を独立させ、問題時は2環境の既存経路を変更せずCodex分岐だけをrevertできる設計にする。
- **依存**: CORE-DSC-001〜006（標準環境ビジョン）、SI-CORE-024（Codexプラグイン配布）。
- **予備判定（推薦）**: **accept 推薦**。3環境での配布と安全機能の同等性を混同すると、Codex利用者に
  存在しない防御を期待させる。完全対応と正式な劣化モードのどちらを採る場合でも、現状差の契約化が必要。
  裁定は人間専用で、本issueは `open` のままとする。
