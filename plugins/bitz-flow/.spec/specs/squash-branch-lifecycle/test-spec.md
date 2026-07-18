# テスト仕様書: squash merge 後のブランチライフサイクル

sdd-test 工程で FLW-FR-001 の EARS 要件から導出した unit-test 検証仕様。

- 実行日: 2026-07-18
- Verification Method: unit-test
- 実行コマンド: `.venv/bin/python -m pytest -q` / `python3 scripts/release_check.py` /
  `python3 scripts/spec inspect --workspace . plugins/*`

## テスト仕様: PR 作成前の branch preflight

- **対象要件**: FLW-FR-001
- **導出元種別**: Event-Driven + Unwanted Behavior
- **テストケース一覧**（`tests/test_branch_preflight.py`）:
  - 新規差分を持つ未使用 head は READY / exit 0
  - 同じ head の merged PR、空差分、open PR の base 不一致・競合は REUSE_BLOCKED
  - mergeability 未確定、git / gh timeout は INDETERMINATE
  - timeout は1〜300秒に限定し、JSON は許可リスト項目だけで生出力・機密値を含まない

## テスト仕様: 証跡付き squash cleanup と冪等再開

- **対象要件**: FLW-FR-001
- **導出元種別**: Event-Driven + State-Driven + Unwanted Behavior
- **テストケース一覧**（`tests/test_worktree_ops.py`）:
  - PR state が MERGED でない場合は worktree / local branch を削除しない
  - initial 状態では PR head SHA・存在 ref・merge commit 到達性を検証後、
    default fast-forward → worktree remove → local branch delete → prune → remote照会の順で進む
  - cleanup-partial / local-cleaned は完了済み段階を skip して前進再開する
  - remote ref が PR head SHA から進行していれば削除せず INDETERMINATE にする
  - remote ref が一致していても期待 SHA・時刻・直前再照会警告を持つ候補報告だけを返し、
    push や削除コマンドを実行・生成しない
  - path escape を含む work-id を副作用前に拒否する
  - 既存 add / list / 非squash cleanup / discard の dry-run、確認フラグ、実動作を維持する

## Skill Validation

- `flow-pr`: frontmatter、発動条件、500行未満、参照先、metadata version 0.2.1 を検査
- `flow-worktree`: frontmatter、発動条件、500行未満、参照先、metadata version 0.2.1 を検査
- 判定: **PASS**。両スキルとも name/フォルダ一致、description の作業・発動条件、
  500行未満（flow-pr 127行 / flow-worktree 123行）、相対参照の実在、単一責務、
  安全確認、semver・author・日付・installed-* 不在を確認した。release_check の
  frontmatter / plugin validate も PASS

## 最終結果

- pytest: **236 passed in 3.66s**
- release_check: **PASS（全チェック合格）**
- spec inspect: **全7ワークスペース PASS**。bitz-flow は問題0・幽霊参照0・孤児要件0
- 検証ステータス: **green**
