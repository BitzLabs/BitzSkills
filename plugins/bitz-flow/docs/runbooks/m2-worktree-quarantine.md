# M2 worktree quarantine runbook

このrunbookはM2 Local Safety Profileのローカル障害復旧だけを扱う。RBAC、通知、鍵管理、remote session、
RTO/SLO、journalのarchive・prune・restoreは対象外である。現在4操作は実装済みだがM2出口裁定までは
gatedであり、production dispatcherは`UNSUPPORTED`を返す。

## 原則

- `doctor` / `audit` / `verify-receipt` はread-onlyで、実行前後のpersistent state digestが一致しなければ
  結果を信用せず`INDETERMINATE`として止める。
- `reconcile`はGitを再実行しない。新しいplan-digestの明示確認後、closure eventとactive marker closure
  だけを追記する。
- worktree、branch、journal、receipt、markerを自動削除・自動解除・自動再実行しない。
- 旧signed capability、capability file、trusted key registry、承認モード宣言がある場合は
  `UNSUPPORTED / unsupported-approval-mode`で即時停止する。plan-digestへ降格しない。

## 手順

1. `worktree doctor --format json`でcurrent bundle、minimum runtime、active marker、journal使用量を確認する。
   `fix-platform-or-bundle`ならbundleやowner-only namespaceを直し、原本は変更しない。
2. `worktree verify-receipt --operation-id <元operation_id> --format json`でchainを検証する。
   `manual-inspection`ならgap、branch、digest/token不一致を人間が確認し、新しい裁定なしでは進めない。
3. `worktree audit --operation-id <元operation_id> --format json`でGit snapshotとchainを照合する。
   判定は`confirmed-complete` / `confirmed-incomplete` / `indeterminate`の3値だけである。
4. `indeterminate`ではGit状態を人間が確認し、decisionは`quarantine`だけを許可する。それ以外はauditの
   classificationと同じdecisionを使う。
5. 次の入力を固定して副作用なしのreconcile planを作る。

   ```text
   worktree reconcile --operation-id <元operation_id> \
     --decision <confirmed-complete|confirmed-incomplete|quarantine> \
     --expires-at <RFC3339 UTC> --nonce <single-use nonce> \
     --bundle-digest <sha256:...> --format json
   ```

6. 出力された新しい`operation_id`、元operation、audit digest、decision、bundle、期限、nonceを照合する。
7. 同じ入力へ`--apply --confirm <新operation_id>`を加えて実行する。target lock下で再観測し、closure確定後に
   target lockを解放してからpromotion lock下でmarkerを閉じる。両lockは同時保持しない。
8. 同じdecisionの再試行は同じclosureへ収束する。異decision、期限切れ、journal head・token・Git stateの
   差替えは`STALE`であり、手順2の新しいauditからやり直す。

## 停止条件

次の場合は`automatic_recovery_allowed: false`を維持し、原本を保持して人間へ戻す。

- `side_effect_state: indeterminate`
- journal gap / branch / digest mismatch / token rollback
- child終了またはGit postconditionを一意に証明できない
- active marker、closure、terminal receiptの参照が競合する
- network/unknown filesystem、owner不一致、durability primitive未確認
- `unsupported-approval-mode`

検証対象と受入行の対応は`references/m2-operability-coverage.json`で確認する。

## worktree root の作成手順（`acl-not-owner-only` の解消）

M2 は worktree root を **owner-only** な local filesystem namespace として信頼する
（`FLW-DSN-017` §1.2）。probe は `st_mode & 0o077` が 0 でなければ
`acl-not-owner-only` で `UNSUPPORTED_FILESYSTEM` へ閉じる。

**既定 umask で `mkdir` した directory は 0755 であり必ず拒否される。**
これは設計どおりの安全側動作であり不具合ではないが、利用者は手順を知らないと復帰できない。

worktree root は **repository の兄弟位置**へ置く（`FLW-DSN-006`）。

```text
<repo-parent>/.worktrees/<repo-slug>-<repo-id8>/<work-id>/
```

repository 内に置くと `git status` や検索結果へ混入し、並行作業の前提が壊れる。
`/tmp` 等の `tmpfs` はマシン再起動で intent record ごと消えるため allowlist 外である。

```text
mkdir -p <repo-parent>/.worktrees
chmod 0700 <repo-parent>/.worktrees
```

確認は doctor で行う。`platform_support` が `SUPPORTED` になれば解消している。

```text
python3 <このスキル>/scripts/flow.py worktree doctor --repo <repo> --format json
```

### 対象外の環境（`chmod` では解消しない理由）

次の理由は permission ではなく環境そのものに起因するため、`chmod` では解消しない。

| 理由 | 意味 | 対応 |
|---|---|---|
| `platform-out-of-scope` | 保証対象は当面 Linux のみ（裁定 2026-08-24） | Linux 上で実行する |
| `case-insensitive-unsupported` | case-insensitive volume は `collision_key` の folded component を導出できない | case-sensitive な filesystem 上へ置く |
| `filesystem-type-not-allowlisted` | 同梱 allowlist（btrfs / ext4 / xfs）外。`tmpfs` は再起動で消えるため含まない | 永続 filesystem 上へ置く |
| `filesystem-class-network` | network filesystem は lock semantics を保証できない | local filesystem 上へ置く |

公開 result の `data.required_human_input` に、対象 path と必要な是正が載る。
`data.evidence` には判定理由がそのまま入る。
