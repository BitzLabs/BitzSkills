---
id: SI-ENV-005
raised_by: sdd-review 第2ラウンド クロスモデル（agy/Gemini）AGY-5
target: plugins/bitz-env/skills/env-orchestration/references/collab-contract.md + ENV-FR-006
proposed_change_type: bump
status: proposed
---
- **矛盾/曖昧の内容**: 協調アダプタ契約 第1項は標準スキルセットを固定名（delegate / review /
  status）で要求するが、複数のアダプタプラグイン（agy 用・codex 用など）が同名ツールを
  レジストリへ登録すると、グローバル名前空間で衝突する（上書き・実行時エラー・意図せぬ
  別モデルの呼び出し）。「アダプタゼロでも機能する純粋追加式」を謳いながら、アダプタを
  2つ追加した瞬間に破綻する構造。固定名による契約と疎結合が両立していない。
- **提案する修正**:
  (a) 契約を改訂: アダプタのツール名は固有プレフィックス必須（例 `bitz_<name>_delegate`）とする。
  (b) env-register がレジストリに「標準の役割（delegate 等）→ 実際のツール名」への
      ルーティングテーブルを記録し、env-orchestration はそれ経由で委譲先を解決する。
  (c) 登録時に名前衝突を検出したらプレフィックスで名前空間化し、優先順を明示する。
- **影響推定**: collab-contract.md（公開契約）の改訂 → Design Gate 対象・軽量レーン禁止。
  ENV-CON-002（後方互換）に留意し、固定名を前提にした既存アダプタを非準拠化するため
  契約バージョン更新と移行方針を伴う。ENV-FR-006 にルーティング受入基準を追加。
