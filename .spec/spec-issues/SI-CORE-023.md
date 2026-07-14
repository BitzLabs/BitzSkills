---
id: SI-CORE-023
raised_by: 2026-07-14 SI-CORE-021 開発の振り返り（毎回 --workspace で回避）
target: ルート単体 spec_inspect が ENV-* 幽霊参照で常時 FAIL（--workspace でのみ PASS）
proposed_change_type: fix
status: accepted
---
- **目的**: ルート単体の `spec_inspect .` が `ENV-*` 幽霊参照で**常時 FAIL** し、`--workspace . plugins/*`
  でのみ PASS になる。既定の実行が誤った赤を出し、root の `inspection-report.md` が実行モードで
  PASS/FAIL 揺れる。誤解を招かない状態にする。
- **背景（実事例）**: 2026-07-14 の SI-CORE-021 開発で、`spec_inspect .`（単体）は
  `ENV-CON-001`/`ENV-FR-001`/`ENV-FR-002`/`ENV-FR-008`/`ENV-NFR-001` の幽霊参照5件で FAIL。
  これらは `tests/test_env_guard.py`（ルート）が参照するが、実体は `plugins/bitz-env/.spec` にあるため
  単体モードでは未解決。`--workspace . plugins/*` では解決して PASS。検証のたびに `--workspace` へ
  切替えて回避した。
- **提案する修正（人間が取捨選択）**:
  1. **ルート側の参照整理**: `tests/test_env_guard.py` が別ワークスペースの `ENV-*` を参照している
     構造を見直す（ルート workspace が持つべき ID か、bitz-env 側へ寄せるべきか）。
  2. **または既定実行の明確化**: このモノリポの正規の検証コマンドを `--workspace . plugins/*` と定め、
     単体 `spec_inspect .` を使わない旨を AGENTS.md / sdd-core に明記。root inspection-report の
     生成も正規コマンド基準に統一。
  3. **（任意・SI-SDD 派生）** `spec_inspect` がモノリポ配置（複数 .spec）を検出したら単体実行時に
     警告する、等のツール側改善。
- **対象ファイル**: `tests/test_env_guard.py`（参照整理案）、`AGENTS.md`/`.spec/PROJECT.md`（正規コマンド明記）、
  必要なら `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py`（SI-SDD へ派生）。
- **確認観点**:
  - 正規の検証コマンドで安定して PASS すること
  - 幽霊参照の赤が「本物の問題」と「モノリポ未解決」で紛れないこと
  - クロスリファレンス検証（--workspace）の意図を壊さないこと
- **影響推定・ロールバック**: 参照整理 or doc 明記が中心。単独 revert 可能。
- **依存**: なし。SI-CORE-021 の検証運用で表面化。
