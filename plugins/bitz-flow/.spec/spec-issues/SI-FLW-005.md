---
id: SI-FLW-005
raised_by: PR #67のpublish/ready/check/merge実運用（2026-07-18）
target: PR公開・CI待機・squash mergeの段階別再開可能ランブック
proposed_change_type: new
status: open
---
- **目的**: PR #67ではpreflight、push、Draft PR作成、ready化、CI待機、squash merge、main同期、
  cleanupを個別コマンドで実施した。PR本文は既存 `pr_helper.py` を使わずshell引数へ直接記述し、
  `gh pr create` / `gh pr merge` はsandboxのネットワーク制限で一度失敗してから権限付き再実行した。
  一発自動化で承認ゲートを消さず、現在状態を外部から再照会して段階別に再開できるランブックを整える。
- **提案する修正**:
  1. `prepare`（preflight・本文生成）、`publish`（push・Draft PR）、`ready`、`await-ci`、`merge`、
     `post-merge-audit` の段階を定義し、各段階が既存PR状態を照会して冪等に再開できるようにする
  2. PR本文は生成専用の `pr_helper.py --output` と `gh pr create --body-file` の利用を標準化し、
     pr_helper自身にはgh実行責務を追加しない
  3. 外部状態変更段階はdry-run既定、`--execute`と必要な人間承認を維持し、CI green前のmergeを拒否する
  4. sandbox/network denied、GitHub到達不能、未認証、CI失敗、既存Draft、既mergeを区別して診断する
  5. cleanupはSI-FLW-003/004へ委譲し、remote deleteをpublish/mergeランブックへ混在させない
- **対象ファイル**: `plugins/bitz-flow/skills/flow-pr/SKILL.md`、同skill配下の新規段階オーケストレータ候補、
  `pr_helper.py`は必要なら出力契約のみ、関連テスト、flow-worktreeとの接続説明、bitz-flowマニフェスト。
- **確認観点**: 既存PRを重複作成しないこと。CI未完了・失敗でmergeしないこと。PRタイトルとsquash subjectを
  Conventional Commitsで一致させること。外部状態変更ごとに承認境界を保ち、資格情報を記録しないこと。
- **影響推定・ロールバック**: 新規のGitHub状態変更ランブックで影響が大きく、通常SDDフロー +
  Design Gate必須。段階オーケストレータとSKILL参照を一括revertし、既存の手動flow-prへ戻せる。
- **依存**: SI-FLW-002（preflight診断）、SI-FLW-003（監査）、SI-FLW-004（branch-only cleanup）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。pr_helperの生成専用契約と人間承認を維持する |
| ガードレール抵触 | 条件付きでなし。外部変更・merge・削除の自動連結は禁止する |
| 影響範囲 | flow-prの公開運用契約、新規オーケストレータ、flow-worktree接続 |
| 軽量レーン適否 | 不適。GitHub外部状態を変更する新規契約 |

**推薦: accept**。手順は定型だが、現状は中断再開・引用・障害分類を毎回人手で組み立てているため。
