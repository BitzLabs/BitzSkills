---
name: flow-core
description: Git / GitHub 操作の唯一の実行入口。git status / diff / log / branch / commit / worktree、GitHub の Issue / PR / merge / CI / release / CHANGELOG に触れる前に必ず発動する。生の git・gh コマンドを直接実行せず、同梱の dispatcher（flow.py）を実行して結果を受け取る。リポジトリの状態取得と状態変更のどちらにも使う。「開発」一般ではなく、Git / GitHub の状態を読む・変えるときに使う。
metadata:
  version: "0.4.1"
  author: br7.hide
  created: "2026-07-31"
  updated: "2026-08-03"
---

# flow-core — Git / GitHub 操作の単一入口

## 1. Mandatory entry protocol

1. **Git / GitHub の操作は `flow.py` を使う。**

   ```bash
   python3 <このスキル>/scripts/flow.py [--repo PATH] [--format compact|json] <domain> <action> [options]
   ```

2. **生コマンドへ戻らない。** `git` / `gh` を直接実行しない。`flow.py` が扱えない操作を
   自前のコマンドで代替しない。
3. **`UNSUPPORTED` なら停止する。** 終了コード 8 が返ったら、その場で作業を止め、
   「どの操作が未対応だったか」を利用者へ報告する。回避策を自作しない。
4. 最初の操作はローカル Git の読取なら `repo inspect`、GitHub 側の書込みが要るなら
   `repo capabilities`、明示的な診断依頼なら flow-doctor を使う。
   毎回の操作前に診断を挟まない。

## 2. Intent routing

| 利用者の意図 | domain | action |
|---|---|---|
| リポジトリの素性・現在地を知る | `repo` | `inspect` |
| GitHub 側で何ができるか知る | `repo` | `capabilities` |
| 変更の有無・ブランチ状態を見る | `git` | `status` |
| 何がどれだけ変わったか見る | `git` | `diff-summary` |
| 特定 path の変更内容を見る | `git` | `diff-detail` |
| 履歴・ブランチ一覧・衝突を見る | `git` | `log` / `branches` / `conflicts` |
| remote を取り込む | `git` | `fetch` |
| 変更を記録する | `git` | `stage` → `commit` |
| default へ追従する | `git` | `sync` |
| ブランチを push する | `git` | `publish-branch` |
| 作業を隔離して始める | `worktree` | `plan` → `create` |
| 作業を再開する・一覧する | `worktree` | `resume` / `list` |
| 作業を終う・捨てる | `worktree` | `finish` / `discard` |
| Issue を読む・検索する | `issue` | `list` / `view` / `search` |
| Issue を立てる・更新する | `issue` | `prepare` → `publish` / `edit` / `comment` / `close` |
| 仕様と Issue の対応を確かめる | `issue` | `verify-link` / `reconcile-link` |
| PR を出す | `pr` | `prepare` → `publish` |
| CI とレビューを確認する | `pr` | `checks` / `ready` |
| PR をマージする | `pr` | `merge-plan` → `merge` → `post-merge` |
| リリースを作る | `release` | `plan` → `changelog` → `notes` → `tag-create` → `draft` |

表に無い意図は `flow.py` の対象外である。生コマンドで代替せず、利用者へ相談する。

## 3. Plan / apply rule

状態を変える操作は **plan → 外部裁定 → apply → post-check** の順に進む。

1. まず `--apply` を付けずに実行して plan を得る。plan は対象・前提・副作用の上限・
   必要な承認の強さを返す。
2. `approval` が `explicit-human` の操作は、**利用者本人の明示的な応答を得るまで
   apply しない**。エージェントの判断で代行しない。
3. apply は plan が返した `operation_id` を `--confirm` へ完全一致で渡す。
   `operation_id` は承認の証明ではなく、前提が変わっていないことの照合子である。
4. apply の後は result の `postconditions` を読み、完了を外部状態から確認する。

## 4. Stop conditions

| 終了コード | code | 取るべき行動 |
|---:|---|---|
| 0 | `OK` / `READY` / `DONE` | 続行する |
| 2 | `INVALID_INPUT` | 引数を直して再実行する。パスや ref を推測で補わない |
| 3 | `BLOCKED` | 前提が満たされていない。塞いでいる条件を報告して止まる |
| 4 | `APPROVAL_REQUIRED` | 利用者の明示的な裁定を待つ。自分で承認しない |
| 5 | `UNAVAILABLE` | Git / gh / 認証 / ネットワークの問題。再試行の前に原因を報告する |
| 6 | `STALE` | 前提が変化した。plan からやり直す。古い `operation_id` を再利用しない |
| 7 | `PARTIAL` | 一部だけ完了している。`remaining_steps` を読み、同じ操作を盲目的に再実行しない |
| 8 | `UNSUPPORTED` | 未対応。**停止して報告する。生コマンドで代替しない** |
| 9 | `INDETERMINATE` | 成否が判定できない。reconcile を先に行い、状態を変える操作を続けない |

`truncated` が true のときは省略が起きている。result の `next_actions` が返す絞込み条件で
取り直す。省略されたまま「変更はこれだけ」と判断しない。

## 5. References routing

必要になったものだけを読む。

| 知りたいこと | 参照先 |
|---|---|
| 公開 operation の contract（対象・副作用・承認・再実行可能性） | `<このスキル>/references/operation-catalog.md` |
| result の読み方、終了コード、cause 語彙、snapshot と cursor | `<このスキル>/references/output-contract.md` |
| result の機械可読な形 | `<このスキル>/schemas/result-v1.schema.json` |

## 出力の読み方（compact）

既定の `--format compact` は1項目1行で返る。

```text
OK git.status snapshot=sha256:ab12 branch=feat/x changed=2 ahead=1 behind=0
 M src/a.py
?? tests/test_a.py
NEXT git.diff-summary snapshot=sha256:ab12
```

- 先頭行が判定。`code` と `operation`、失敗時は `cause` と `stage` が付く。
- `NEXT` は次に呼べる操作。shell コマンドではなく domain / action と引数で示される。
  `NEXT` が引数を示したらそのまま渡す（自分で組み立て直さない）。
- `TRUNCATED shown=… total=… cursor=…` が出たら全件ではない。
- **compact のまま読む。** 判断に必要な field はすべて compact に出る。
  `--format json` は result を別のプログラムへ渡すときだけ使う。同じ判定を返すが
  桁違いに長く、文脈を無駄に消費する。自分が読んで判断するなら compact を使う。
