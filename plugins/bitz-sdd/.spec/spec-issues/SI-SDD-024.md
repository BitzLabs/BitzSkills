---
id: SI-SDD-024
raised_by: 2026-07-22 PR #90/#91 並行作成時の採番衝突（開発中に発見）
target: spec_scaffold.py の next_number が並行ブランチで同一 ID を再発行する（採番衝突）
proposed_change_type: modify
status: open
---
- **優先度（推薦）**: **中**。実害は発生済みだが個別には手動採番で回避可能。並行開発
  （worktree / 複数エージェント）を推奨する本リポでは再発頻度が上がるため、重要度は中〜高。
- **目的**: `spec_scaffold.py` の `next_number()`（`plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py`）は
  **対象ディレクトリの `{prefix}-*.md` を glob して `max+1`** で次 ID を決める。この走査は
  **現在のブランチの作業ツリーしか見ない**ため、同一 base（例 origin/main）から派生した2本以上の
  ブランチで並行に起票すると、**すべて同じ番号を返す**。マージ時に add/add コンフリクト、
  最悪は片方を強制解決した際の **ID 二重化**（同一 ID を持つ2ファイル）につながる。
  - **実害**: 2026-07-22、PR #90 と #91 を origin/main 起点で並行作成したところ、両方が
    `SDD-FR-139` と `SDD-TSK-023` を生成した。#91 側を手動で `SDD-FR-140` / `SDD-TSK-024` へ
    採番し直して回避した（要件・タスクの二重定義は spec_inspect が検出できるが、採番段階では防げない）。
  - 同種の「並行ブランチが単調増加の共有リソースを取り合う」問題として version bump もあるが、
    そちらは git が version 行のコンフリクトとして必ず検出できるため本 issue の対象外
    （ID は別ファイル名になりうるため静かに滑り込む点が固有の危険）。
- **提案する修正**（いずれか、または組合せ。設計判断は Design Gate で裁定）:
  1. **重複 ID の機械検出**: `release_check.py`（または spec_inspect）で、同一ワークスペース内に
     同一 ID を持つ成果物が複数無いことを検査する（マージ後の最後の砦。cross-branch は見えないが
     統合時に確実に落とせる）。
  2. **採番の直列化ルールの明文化**: 並行作業（worktree / 複数エージェント並列投入）では
     起票・採番を直列化する、または起票だけ先に main へ land してから分岐する運用を
     `sdd-git` / `flow-worktree` の接続点に規定する（[[pr-unmerged-dependency-no-stacking]] の
     ID 版）。ツール変更なしで再発を大きく減らせる軽量案。
  3. **ID 予約**: spec-issue の受理（accepted 化）時点で要件・タスクの ID レンジを予約する機構を
     `spec_update.py` / `spec_scaffold.py` に持たせる（重いので要否は裁定で判断）。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py`、
  `scripts/release_check.py` または `spec_inspect.py`（重複 ID 検査を採る場合）、
  `plugins/bitz-sdd/skills/sdd-git/SKILL.md` / bitz-flow の `flow-worktree`（直列化ルールを採る場合）、
  対応するテスト、bitz-sdd マニフェスト。
- **確認観点**:
  - 単一ブランチでの通常の連番採番を壊さないこと（回帰）。
  - 重複 ID 検査を入れる場合、既存の正常なワークスペースで誤検出しないこと。
  - 直列化ルールを採る場合、worktree 並列運用（`flow-worktree`）の手順と矛盾しないこと。
- **影響推定・ロールバック**: 案1（重複検査）は release_check に検査追加のみでデータ移行不要。
  案2（ルール明文化）は文書のみ。案3（予約）は採番機構に広く影響。いずれも PR 単位で revert 可能。
- **依存**: [[pr-unmerged-dependency-no-stacking]]（SI-CORE-020、並行 PR の land 順序原則）と論点隣接。
  `flow-worktree`（並列運用の実手順）。
- **予備判定（推薦）**: **accept 推薦**。根拠 — 実害が発生済みで、並行開発を推奨する本リポの運用
  方針と直接衝突する再発型の不備。まずは軽量な案1（重複 ID の機械検出）＋案2（直列化ルール明文化）で
  費用対効果が高い。裁定は人間専用、本 issue は `open` のままとする。
