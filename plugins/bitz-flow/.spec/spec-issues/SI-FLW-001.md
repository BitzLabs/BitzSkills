---
id: SI-FLW-001
raised_by: PR #56/#57/#58 とマージ後ブランチ整理の振り返り（2026-07-18）
target: plugins/bitz-flow/skills/flow-pr・flow-worktree（squash merge後のブランチライフサイクル）
proposed_change_type: modify
status: open
---
- **目的**: squash merge 済みの作業ブランチを次の作業へ再利用すると、元コミットが
  デフォルトブランチの squash commit と祖先関係を持たないため、既反映差分が次の PR に再出現し得る。
  マージ後のブランチを終端として扱い、後続作業の分岐と後片付けを安全かつ再現可能にする。
- **背景（実事故）**: PR #56 を squash merge した後も同じ
  `feat/sdd-accepted-issue-preflight` ブランチへコミットを追加して PR #57 を作成した結果、
  既反映コミットを含む履歴差分により競合した。復旧には最新 `origin/main` から新ブランチを作り、
  未反映の2コミットだけを cherry-pick して PR #58 を作り直す必要があった。さらに後片付けでは、
  `flow-worktree` が「マージ済みなので `git branch -d` で消える」とする一方、squash merge 後の
  元コミットは main の祖先にならないため安全削除判定を通らず、PR の MERGED 証跡を確認した上で
  明示対象へ `-D` を使う必要があった。stale な remote-tracking ref を含む一括リモート削除も失敗し、
  prune 後の再実行が必要になった。
- **提案する修正**:
  1. `flow-pr` に「squash merge 済みブランチは終端であり再利用しない」を追加し、後続作業は
     `git fetch origin` 後の最新デフォルトブランチから新しいブランチを作ることを規定する
  2. PR 作成前に、同一 head ブランチの merged PR の有無、デフォルトブランチとの差分、
     mergeability を再確認し、再利用を検出したら新ブランチへ未反映コミットだけを移す
  3. `flow-pr` / `flow-worktree` のマージ後手順を、PR の `MERGED`・merge commit の
     デフォルトブランチ到達確認 → デフォルトブランチの fast-forward → worktree 除去 →
     ローカルブランチ削除 → remote prune → 実在するリモートブランチの明示削除、の順に統一する
  4. `git branch -D` は squash merge の証跡と削除対象を確定した場合だけ許可し、未マージブランチへ
     誤用しないガードを明記する。SI-CORE-009 の定型処理スクリプトへ実装する場合は dry-run を既定とする
- **対象ファイル**: `plugins/bitz-flow/skills/flow-pr/SKILL.md`、
  `plugins/bitz-flow/skills/flow-worktree/SKILL.md`、必要なら SI-CORE-009 で追加する
  `plugins/bitz-flow/skills/*/scripts/` とそのテスト、bitz-flow のマニフェスト。
- **確認観点**:
  - squash merge 済み head ブランチの再利用を検出し、最新デフォルトブランチからの再分岐を案内できること
  - merge 証跡がないブランチへ `git branch -D` やリモート削除を案内しないこと
  - stale ref と実在 ref が混在しても prune 後に実在対象だけを削除できること
  - SI-CORE-020 の「未マージ依存」規定と矛盾せず、マージ後ライフサイクルとして責務が分離されること
  - skill-validator、`python3 scripts/release_check.py`、
    `python3 scripts/spec inspect --workspace . plugins/*`、関連テストがすべて PASS すること
- **影響推定・ロールバック**: 公開されるエージェント運用契約の変更なので軽量レーンではなく、
  bitz-flow ワークスペースの通常 SDD フロー + Design Gate を推奨する。`--impact CORE-FR-014` では
  bitz-flow 内の直接依存成果物は0件であり、同要件を改訂せず FLW 要件として追加できる。
  変更は flow-pr / flow-worktree と任意の補助スクリプトに閉じ、一括 revert で現行手順へ戻せる。
- **依存**: SI-CORE-010（sdd-git を bitz-flow への委譲ポインタへ縮退し、Git フローの正を一本化）。
  SI-CORE-010 は SI-CORE-009 に依存するため、推奨順序は SI-CORE-009 → SI-CORE-010 → 本 ISSUE。
- **予備判定（推薦）**: **accept 推奨**。PR 作り直しと削除再実行が実際に発生しており、
  現行手順には squash merge の履歴特性と矛盾する記述がある。既存 SI-CORE-020 は未マージ依存を
  対象とするため重複せず、ガードレールを弱めずに誤再利用・誤削除の両方を予防できる。
