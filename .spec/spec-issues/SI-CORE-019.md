---
id: SI-CORE-019
raised_by: SI-CORE-011 実装中の spec_inspect 実行で発見（2026-07-13 チャットセッション）
target: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py（単体実行時のクロスワークスペース参照の扱い）と検証運用ドキュメント
proposed_change_type: bump
status: accepted
---
- **目的**: `spec_inspect.py` を**リポジトリルート単体**（`spec_inspect.py .`）で実行したとき、
  ルートの `tests/` から `plugins/*/.spec/` の要件（例: `tests/test_env_guard.py` → `ENV-FR-001` ほか）への
  **正当なクロスワークスペース追跡参照**が「幽霊参照」として偽陽性報告される問題を解消する。
- **発見の経緯・実測**:
  - `spec_inspect.py .`（root 単体）→ 幽霊参照 5件（`ENV-CON-001` / `ENV-FR-001` / `ENV-FR-002` /
    `ENV-FR-008` / `ENV-NFR-001`、いずれも `tests/test_env_guard.py` 由来）。
  - `spec_inspect.py --workspace . plugins/*`（モノレポ一括）→ **幽霊参照 0件**（正しく解決）。
  - これらは fixture ではなく bitz-env の**実要件へのトレーサビリティ参照**（`対応要件: ENV-FR-001` 等）であり、
    連結記法での隠蔽（test_spec_inspect.py の流儀）はトレース情報を壊すため不適。
  - CI / `release_check.py` は spec_inspect を実行しないため**CI ゲートには影響しない**。
    影響は「エージェント/人間が root 単体で手動 inspect したときの誤解」に限定される（実際に本セッションで誤認が発生）。
- **提案する修正（いずれか。人間裁定）**:
  1. **運用・ドキュメント明確化（低リスク・推奨候補）**: このモノレポの正典 inspect コマンドは
     `spec_inspect.py --workspace . plugins/*`（クロスリファレンス解決込み）であることを、
     sdd-core SKILL.md の「検証ツール」節・AGENTS.md の検証手順で**単体実行より優先**と明記する。
     併せて `.spec/inspection-report.md` の再生成も一括モードで行う運用に統一する。
  2. **ツール改善（任意・別途テスト先行）**: `spec_inspect.py` に既知の姉妹ワークスペースの
     ID プレフィックス（`ENV-` / `DDD-` / `PLG-` / `SKC-` 等）を渡された場合、単体実行でも
     それらへの参照を幽霊参照から除外する（`--siblings` 相当のヒント、または実行ディレクトリからの推定）。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/SKILL.md`、`AGENTS.md`（検証手順）、
  （案2採用時のみ）`plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py` + `tests/`、bitz-sdd マニフェスト bump。
- **確認観点**:
  - 採用案で `spec_inspect` の正典手順を踏めば `tests/` 由来の偽陽性が出ないこと
  - 真の幽霊参照（実在しない ID への参照）は引き続き検出されること（案2採用時はテストで担保）
  - release_check / spec_inspect（一括）PASS
- **影響推定・ロールバック**: 案1は文書変更のみ・単独 revert 可。案2はツール追加変更＋テストで revert 可。
- **依存**: なし。SI-CORE-007（プラグイン間依存の検証機構）と論点が隣接するため、
  採用時は整合を取る（クロスワークスペース参照の解決方針を共通化）。
- **裁定（2026-07-13, 人間）**: **案1（運用・ドキュメント明確化）** を採用。正典 inspect コマンドを `--workspace . plugins/*` と SKILL.md / AGENTS.md に明記する。案2（ツール改修）は当面見送り。
