---
id: FLW-DSN-001
title: "squash merge 後のブランチライフサイクル"
status: active
version: 1.0
updated: 2026-07-18
owner: hide
implements: FLW-FR-001
origin: SI-FLW-001
---

# FLW-DSN-001 squash merge 後のブランチライフサイクル

## 1. 背景と不変条件

squash merge は作業ブランチ上の複数コミットを、デフォルトブランチ上の新しい1コミットへ置換する。したがって、マージ後も元コミットはデフォルトブランチの祖先にならず、通常の `git branch -d` は安全削除判定を通らない。さらに同じ head ブランチを後続 PR に再利用すると、既反映コミットが履歴差分へ再出現する。

本設計では次を不変条件とする。

- squash merge 済み head ブランチは終端であり、後続作業へ再利用しない
- `git branch -D` は GitHub の MERGED 証跡、PR の最終 head SHA と全対象 ref の一致、merge commit のデフォルトブランチ到達をすべて確認した経路からだけ実行する
- 証跡を取得できない場合は「未マージ」と同じ安全側停止にする
- remote ref は prune 後に実在と SHA を照会する。本リポジトリのガードレールが期待 SHA 付き強制更新も許可しないため、競合更新を原子的に防げない自動 remote delete は行わず、削除候補と確認手順だけを報告する
- 既存の失敗時 discard はマージ後 cleanup と別の状態遷移として維持する

## 2. 状態モデル

| 状態 | 証跡 | 許可する操作 |
|---|---|---|
| active | 同一 head の merged PRなし、差分あり、open PRがあればbase一致かつ競合なし | PR 作成・作業継続 |
| preflight-blocked | merged PR、空差分、base不一致、競合のいずれか | 通常続行を拒否し、再分岐または修正を案内 |
| terminal-squashed | PR state=MERGED、head名一致、PR head SHAと全対象ref一致、merge commit到達済み | 新規作業の再利用拒否、安全なローカル cleanup |
| cleanup-partial | worktree除去済み、local branchはPR head SHAのまま存在 | 完了済み段階をskipしてlocal cleanupを再開 |
| local-cleaned | worktreeとlocal branchがともに不存在、PR証跡は有効 | remote refの照会・候補報告だけを実行 |
| indeterminate | GitHub照会失敗、head SHA不一致、merge commit欠落、worktree対応不一致、到達性不成立 | 削除せず停止・人間確認 |
| failed-unmerged | マージ証跡なしで作業失敗を人間が確認 | 既存 discard フロー |

`terminal-squashed` と `failed-unmerged` はどちらも `git branch -D` を使いうるが、前者はマージ証跡、後者は失敗作業を破棄する明示確認を根拠とし、CLI と説明を混在させない。

## 3. コンポーネント設計

### 3.1 flow-pr の branch preflight

`flow-pr/scripts/branch_preflight.py` を読み取り専用の事前検査として追加する。候補ブランチについて、同じ head の merged PR、`origin/<default>` との差分と ahead/behind、同じ head の open PR がある場合は base・`mergeable`・`mergeStateStatus` を照会し、結果を次の終了コードへ正規化する。Draft PR 作成前で open PR がない場合は mergeability を N/A として報告し、作成後の再実行で検査する。

CLI は `--branch`、`--default-branch`、`--repo`、`--timeout-seconds`、`--json` を持つ。timeout は既定30秒、1〜300秒の整数だけを受理する。JSON は判定、終了コード、branch、default branch、merged/open PR番号、ahead/behind、差分有無、base、mergeability、検査時刻（UTC）、失敗した検査名だけを許可リストから構成し、git / gh の raw stdout・stderr、環境変数、資格情報は含めない。

| 終了コード | 判定 | 動作 |
|---:|---|---|
| 0 | READY | merged PRなし、差分あり、open PRがあればbase一致かつ競合なし。通常フローを続行可能 |
| 2 | INDETERMINATE | git/gh失敗、JSON不正、mergeability不明。安全側停止して人間確認 |
| 3 | REUSE_BLOCKED | merged PR、空差分、base不一致、競合のいずれか。最新 origin のデフォルトブランチから新ブランチを作る案内 |

スクリプトはブランチ作成・cherry-pick・push を実行しない。未反映コミットの選別は履歴と tree diff を人間が確認する必要があり、自動選別すると既反映差分の再混入を保証できないためである。flow-pr は `git fetch origin` 後に `origin/<default>` から新ブランチを作り、確認済みの未反映コミットだけを明示 SHA で移す復旧手順を規定する。

### 3.2 worktree_ops の guarded squash cleanup

既存 `cleanup` に `--squash-pr <number>`、`--default-branch <name>`、`--timeout-seconds <N>`、`--json`、任意の `--actor <label>` を追加する。`--squash-pr` 指定時だけ squash cleanup 経路へ入る。timeout は既定30秒、1〜300秒の整数だけを受理する。

最初に削除対象の存在状態を分類し、その後、すべての状態で共通する証跡を検証する。

1. work-id が単一パス要素であり、解決後パスが `<repo>-wt/` 直下にあることを確認する
2. branch と default branch を `git check-ref-format --branch` で検査し、両者が同一なら拒否する
3. `git worktree list --porcelain` と local ref の有無から initial / cleanup-partial / local-cleaned / invalid を分類する
4. 呼出元リポジトリがデフォルトブランチ上かつ作業ツリーが clean であることを確認する
5. `git fetch --prune origin` を実行する
6. `gh pr view <number> --json state,headRefName,headRefOid,mergeCommit` を取得する
7. state=MERGED、headRefName=対象 branch、headRefOid、mergeCommit.oid が存在することを確認する
8. 存在する worktree・local ref・remote ref だけを headRefOid と照合する。不在対象は状態表の完了済み条件に合う場合だけskipする
9. `git merge-base --is-ancestor <mergeCommit.oid> origin/<default>` で到達性を確認する

状態別の必須証跡は次のとおり。

| 分類 | 存在状態 | 必須証跡 | 次の操作 |
|---|---|---|---|
| initial | worktreeあり・localあり | worktree path/branch/HEADとlocal SHAがheadRefOid一致 | 通常cleanup |
| cleanup-partial | worktreeなし・localあり | 同じbranchを使う別worktreeなし、local SHAがheadRefOid一致 | worktree除去をskip |
| local-cleaned | worktreeなし・localなし | 同じbranchを使うworktreeなし、PR証跡とremote SHA検証は必須 | local操作をskip |
| invalid | worktreeあり・localなし、管理外path、存在refのSHA不一致 | なし | 副作用なしで停止 |

検証完了後の状態変更は次の順序で行う。

1. `git merge --ff-only origin/<default>` でローカルのデフォルトブランチを更新する
2. worktree が存在すれば除去し、既に無ければ完了済みとして skip する
3. 対象ローカル branch が headRefOid のまま存在すれば `git branch -D` で削除し、既に無ければ skip する
4. `git fetch --prune origin` 後に `git ls-remote --heads origin refs/heads/<branch>` を実行する
5. remote ref が無ければ完了、headRefOid と異なれば INDETERMINATE、同じなら削除候補として JSON と人間可読出力へ記録する。候補には検査時刻と「削除操作の直前に再照会し、期待SHAと異なれば中止する」警告を付け、削除コマンド自体は生成しない

各外部コマンドに timeout を適用する。JSON は PR番号、branch、PR head SHA、merge commit、default branch、状態分類、各検証結果、完了・skip・未完了段階、検査時刻（UTC）、任意の actor label だけを許可リストから構成する。git / gh の raw stdout・stderr、token・credential・環境変数値は含めない。

### 3.3 冪等再開

cleanup はロールバックで削除済み ref を再生成せず、前進再開する。再実行時は各段階の存在状態を照会し、次のように扱う。

| 部分状態 | 再実行時の扱い |
|---|---|
| initial | 全共通検証と存在対象のSHA照合後に通常実行 |
| cleanup-partial | 全共通検証とlocal/remote SHA照合後、worktree除去をskipして続行 |
| local-cleaned | 全共通検証とremote SHA照合後、ローカルcleanupをskipして候補報告へ進む |
| invalid | 管理状態不整合として停止し、人間確認を求める |
| remote refがheadRefOidから進行 | 削除候補にせず停止し、新しい作業として保全する |

この再開状態機械と timeout を故障注入テストで固定する。

既存 `cleanup` の非 squash 経路は `git branch -d` の Git 安全判定を維持する。flow-worktree の標準手順は squash cleanup 経路へ切り替え、非 squash 経路は互換性のため残す。

## 4. 安全性と失敗時動作

- `--execute --yes` の二重確認は維持する
- 証跡検証は削除操作より前に完了させ、途中失敗時に削除コマンドへ到達しない
- GitHub CLI が未導入・未認証・通信失敗の場合は exit 2 とし、ローカル履歴だけから MERGED を推測しない
- remote branch が既に削除済みなら正常な skip とし、実在する ref は期待 SHA・検査時刻・再照会必須の警告とともに報告するだけで、自動削除も削除コマンド生成も行わない
- work-id のパス境界、Git ref 書式、default branch 保護、worktree path・branch・HEAD の一致を副作用前に検証する
- timeout と途中失敗は INDETERMINATE とし、構造化出力に完了済み段階と再開方法を含める
- 禁止操作 `git reset --hard` / `git push --force` / `git clean -f` / `rm -rf` / `sudo` は追加しない

## 5. 代替案と却下理由

| 案 | 判定 | 理由 |
|---|---|---|
| SKILL.md の注意書きだけ追加 | 却下 | PR 作成前と削除前の判定が人間・エージェントの記憶に依存し、同じ事故を機械的に止められない |
| pr_helper.py に GitHub 照会を追加 | 却下 | CORE-FR-015 が定める「PR本文を生成するだけ」の責務と外部コマンド非実行契約を壊す |
| cleanup を常に `git branch -D` に変更 | 却下 | MERGED 証跡がない未マージブランチまで削除でき、ガードレールを弱める |
| 期待 SHA 付き `--force-with-lease` で remote delete | 却下 | Git の条件付き更新としては有効だが、本リポジトリの `git push --force` 系禁止と既存静的ガードに抵触するため採用しない |
| 専用 preflight + 証跡付きローカル cleanup + remote候補報告 | 採用 | 読み取り専用判定と状態変更操作を分離し、競合更新を破壊せず既存スクリプト契約を保てる |

## 6. 影響範囲とロールバック

- 変更対象: flow-pr / flow-worktree の SKILL.md、branch_preflight.py、worktree_ops.py、関連テスト、bitz-flow の3マニフェスト
- 変更しない対象: flow-core のフロー選択、pr_helper.py の生成専用契約、discard の失敗時破棄契約、bitz-sdd の sdd-git
- ロールバック: branch_preflight.py と squash cleanup 経路、SKILL.md の参照を同一 PR で revert する。運用途中失敗は削除済み ref を再生成せず、3.3 の冪等再開で収束させる。既存 cleanup / discard の非 squash CLI は残るためデータ移行は不要

## 7. 検証設計

- branch preflight: merged 0件・1件・複数件、差分なし、ahead/behind、open PR の base・mergeability、git/gh失敗、不正JSON、timeout、許可リストJSON診断を subprocess モックで検証する
- guarded cleanup: MERGED、未マージ、PR head SHA と worktree/local/remote の不一致、merge commit欠落、到達性不成立、入力path/ref不正、dirty/default branch不一致を検証し、失敗時に削除副作用がないことを確認する
- 冪等再開: 各状態変更段階の故障注入、完了済み段階のskip、timeout、JSON診断を検証する
- remote cleanup: prune 後の ref なしは skip、ref ありは SHA 一致時も報告だけで自動削除しないことを検証する
- 互換性: 既存 add/list/非squash cleanup/discard の引数、dry-run、確認フラグ、終了コードを固定する
- 契約検証: skill-validator、pytest、release_check、`spec inspect --workspace . plugins/*` を実行する

## 8. Design Gate 裁定記録

2026-07-18、ユーザー `hide` が次の設計を一括承認し、Design Gate を通過した。

1. 専用の読み取り専用 `branch_preflight.py` で merged PR・差分・mergeability を検査する
2. `worktree_ops.py cleanup` に PR head SHA・worktree境界・冪等再開・timeout・JSON診断を持つ squash 経路を追加し、既存非 squash 経路は互換維持する
3. GitHub CLI で証跡を取得できない場合は削除・再利用を許可せず安全側停止する
4. remote branch は自動削除せず、prune・実在確認・期待 SHA 付き候補報告までを自動化する
