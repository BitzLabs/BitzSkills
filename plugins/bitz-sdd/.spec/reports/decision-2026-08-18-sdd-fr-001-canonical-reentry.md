# 裁定記録 — SDD-FR-001 の正規複数 workspace 検査を修正する

- **日付**: 2026-08-18
- **裁定者**: hide（対話での「お願いします」）
- **対象**: `SDD-FR-001`

## 裁定

`SDD-FR-001` を `verified → implementing` へ戻し、正規の複数 workspace 検査で
他 workspace に実在するタスク ID を幽霊参照と誤判定する不具合を修正する。

## 理由

`python3 scripts/spec inspect --workspace . plugins/* --check-only` は、要件 ID を全 workspace から
集約する一方、タスク ID は検査中の workspace 内だけを既知として扱う。そのためルート workspace の
テスト仕様が bitz-flow workspace の実在タスクを参照すると、存在しない参照として FAIL する。

これは `SDD-FR-001` の「実在するタスク ID は幽霊判定から除外し、存在しないタスク ID は引き続き
検出する」という既存契約の未達であり、新要件ではなく同要件の再実装・再検証として扱う。

## 実施条件

1. 複数 workspace 検査では、検査対象すべての `.spec/tasks/*.md` の stem を既知 ID とする。
2. 単一 workspace 検査の既存挙動は維持する。
3. 検査対象のどこにも存在しないタスク ID は引き続き幽霊参照として FAIL する。
4. 正規検査、関連 pytest、全 pytest、release check を再実行する。
