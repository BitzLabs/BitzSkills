# Operation Catalog

公開 operation の contract。**この表にない operation は `UNSUPPORTED`**（exit 8）を返して停止し、
生の `git` / `gh` コマンドを代替案として提示しない。

現在**公開**されているのは **M0 read-only 3 operation だけ**である
（`repo.inspect` / `git.status` / `git.diff-summary`）。公開集合の正は
`scripts/flowlib/cli.py` の `PUBLISHED_OPERATIONS`（`_HANDLERS` との一致を import 時に強制）。

M2 worktree operation は実装済みだが、M2 出口が未達（`FLW-REV-016` FAIL）のため
**2026-08-15 の裁定で公開集合から外した**（縮退規則3 の適用。裁定記録は
`.spec/reports/decision-2026-08-15-m0-shipping-surface-and-m2-rescope.md`）。
現在は `UNSUPPORTED` を返す。契約は凍結済みで下節に残す。

M1 のoperationは**契約だけを凍結済み**で、Completion Gate裁定までは公開しない
（下の「M1で凍結した契約（未公開）」節）。
凍結は「後から意味を変えないための固定」であって公開予告ではない。実装と fault fixture が
揃うまで、これらの operation は `UNSUPPORTED` を返す。

## 共通 contract の field

各 operation は次の 11 field を持つ。

| field | 内容 |
|---|---|
| `operation` | `<domain>.<action>` の安定名 |
| `class` | `read` / `local-write` / `remote-write` / `destructive` |
| `target` | repo identity、ref、path 等の canonical target |
| `preconditions` | plan 時と apply 直前に照合する事実 |
| `effects` | 許可された副作用の上限。列挙外は実行しない |
| `approval` | `none` / `mutation` / `external-write` / `explicit-human` |
| `postconditions` | 完了を外部状態から一意に判定する条件 |
| `retry` | `safe` / `reconcile-first` / `manual-only` |
| `concurrency_key` | 同じ target へ同時 write させない直列化キー |
| `partial` | 完了段階と残存段階 |
| `evidence` | result へ残す秘密値を含まない証跡 |

`approval` は CLI が人間本人を認証したことを表さない。実行前に必要な**外部裁定の強さ**を表す。

## 公開 operation（M0）

### `repo.inspect`

| field | 値 |
|---|---|
| `class` | `read` |
| `target` | canonical repo root |
| `preconditions` | 対象パスが Git work tree に属する |
| `effects` | なし（空配列） |
| `approval` | `none` |
| `postconditions` | snapshot 付き result を返す |
| `retry` | `safe` |
| `concurrency_key` | `null` |
| `partial` | なし（単一段階） |
| `evidence` | repo root、HEAD SHA、branch、upstream、remote の canonical identity |

Git 入力は `rev-parse` と `status --porcelain=v2 --branch -z`。
remote は URL をそのまま返さず host / owner / repo へ正規化する（credential を埋め込んだ URL を
出力しないため）。data schema は `schemas/operations/repo.inspect.schema.json`。

### `git.status`

| field | 値 |
|---|---|
| `class` | `read` |
| `target` | canonical repo root |
| `preconditions` | 対象パスが Git work tree に属する |
| `effects` | なし（空配列） |
| `approval` | `none` |
| `postconditions` | snapshot 付き result を返す |
| `retry` | `safe` |
| `concurrency_key` | `null` |
| `partial` | なし（単一段階） |
| `evidence` | branch、upstream、ahead / behind、変更種別ごとの件数 |

Git 入力は `status --porcelain=v2 --branch -z`。path は NUL 区切りで取得し、改行・空白・
非 ASCII を含む filename を損なわない。data schema は `schemas/operations/git.status.schema.json`。

### `git.diff-summary`

| field | 値 |
|---|---|
| `class` | `read` |
| `target` | canonical repo root と比較 range |
| `preconditions` | 対象パスが Git work tree に属する |
| `effects` | なし（空配列） |
| `approval` | `none` |
| `postconditions` | snapshot 付き result を返す |
| `retry` | `safe` |
| `concurrency_key` | `null` |
| `partial` | なし（単一段階） |
| `evidence` | 変更件数、path、変更種別、追加削除行数、binary 判定 |

Git 入力は `diff --name-status -z` と `diff --numstat -z`。
変更行の内容は返さない（必要なら M1 の `git.diff-detail` を使う）。
data schema は `schemas/operations/git.diff-summary.schema.json`。

## M2 worktree の契約（未公開・`UNSUPPORTED`）

実装済みだが M2 出口通過まで公開しない（2026-08-15 裁定）。
`worktree.finish` / `worktree.discard` は同裁定で **M3 へ移送**した。

| operation | class | approval | effects | retry |
|---|---|---|---|---|
| `worktree.audit` | read | none | なし | safe |
| `worktree.create` | local-write | explicit-human | branchとworktree作成 | reconcile-first |
| `worktree.resume` | local-write | explicit-human | resume receipt追記 | reconcile-first |
| `worktree.finish` | destructive | explicit-human | merged worktreeとlocal branch除去 | reconcile-first |
| `worktree.discard` | destructive | explicit-human | retention ref作成後にworktreeとlocal branch除去 | manual-only |

writeは副作用なしのplanで`operation_id`と`capability_context`、`approval_mode`を返す。
applyの要求は承認モードで決まる（`SI-FLW-061`）。既定の`plan-digest`では同じ入力と
`--confirm <operation_id>`だけを要求し、nonceは`operation_id`から導出する。
trusted key registryがある配備では`signed-capability`となり`--capability-file`も要求する。trusted Ed25519 public keyは
Git common-dirの`bitz-flow-v2/trusted-worktree-keys.json`からだけ読み、CLI引数で差し替えない。
registryはowner-only regular fileでなければならない。各mutation直前に署名・期限・scope・identityを
再検査し、nonceを永続消費する。receiptはcommon-dir配下へhash-chainでfsyncし、部分失敗は
completed/remaining stepsを返してquarantineする。remote writeはM3まで`UNSUPPORTED`を維持する。

## M1 で凍結した契約（未公開）

`FLW-DSN-015` と `FLW-DSN-005` を正として contract を固定する。**公開は M1-3 / M1-4 以降**であり、
それまでは `UNSUPPORTED`（exit 8）を返す。write の状態機械・target guard・intent record の規律は
`FLW-DSN-015`、recovery class の決定表は `references/recovery-matrix.md` が正。

### class / approval / retry / concurrency_key

| operation | class | approval | retry | concurrency_key | 公開 milestone |
|---|---|---|---|---|---|
| `git.diff-detail` | `read` | `none` | `safe` | `null` | M1-4 |
| `git.log` | `read` | `none` | `safe` | `null` | M1-4 |
| `git.branches` | `read` | `none` | `safe` | `null` | M1-4 |
| `git.conflicts` | `read` | `none` | `safe` | `null` | M1-4 |
| `worktree.list` | `read` | `none` | `safe` | `null` | M1-4 |
| `repo.doctor` | `read` | `none` | `safe` | `null` | M1-4 |
| `git.fetch` | `local-write` | `mutation` | `reconcile-first` | remote-tracking ref 集合 + `FETCH_HEAD` | M1-4 |
| `git.stage` | `local-write` | `mutation` | `reconcile-first` | common-dir + worktree ID で識別した index | M1-3 |
| `git.commit` | `local-write` | `mutation` | `reconcile-first` | branch ref と同一 worktree の index | M1-3 |
| `git.sync` | `local-write` | `mutation` | `reconcile-first` | branch ref、index、remote-tracking ref 集合 | M1-4 |
| `git.publish-branch` | `remote-write` | `explicit-human` | `manual-only` | repository ID + remote branch ref | M1-4 |
| `git.delete-remote-branch` | `destructive` | `explicit-human` | `manual-only` | repository ID + remote branch ref | M1-4 |

`repo.doctor` の operation 名は `FLW-FR-011`（flow-doctor v2）から起こした。設計側が
domain を明示していないため、既存の domain 閉集合（`repo` / `git` / `worktree` / `issue` / `pr` /
`release`）のうち診断対象（repository と実行環境）に最も整合する `repo` を採った。
M1-4 実装時に設計と齟齬が出た場合は spec-issue を起票して裁定を仰ぐ。

### 追加 read operation

`target` は canonical repo root（`worktree.list` は共通 common-dir）、`preconditions` は
「対象パスが Git work tree に属する」、`effects` は空配列、`postconditions` は
「snapshot 付き result を返す」、`partial` はなし（単一段階）で M0 の read と共通である。
`evidence` だけが operation ごとに異なる。

| operation | Git 入力 | `evidence` |
|---|---|---|
| `git.diff-detail` | `diff --no-ext-diff --unified=1` | 指定 path / hunk の変更行、最大 bytes・最大 hunks と超過の明示 |
| `git.log` | `log --format` + NUL separator | short SHA、subject、author date、parents |
| `git.branches` | `for-each-ref --format` | local / remote、SHA、upstream、ahead / behind |
| `git.conflicts` | `diff --name-only --diff-filter=U -z` | conflict path 一覧 |
| `worktree.list` | `worktree list --porcelain` | path、HEAD、branch、locked / prunable |
| `repo.doctor` | 各 CLI の version / capability 照会 | operation 別 capability（必要 version、scope、filesystem、locking、process tree 収束）、不足 stage と許可語彙 cause |

`git.diff-detail` は `diff-summary` と同じ snapshot fingerprint 規約に従い、呼出時の `--snapshot` と
再計算値が違えば `STALE` を返す。`repo.doctor` は対象 project・Git ref・GitHub 状態を変更せず、
GitHub を使わない対象での `gh` 欠如は warning として返す。

### write operation

すべて plan / apply を分離し、plan は副作用なしで `target` / `preconditions` / `effects` /
`postconditions` / `approval` / `operation_id` を返す。plan が列挙した `effects` が apply の上限であり、
列挙外は実行しない。apply は `operation_id` と `snapshot` の一致を要求し、不一致なら**副作用 0 で**
`STALE` を返す。

| operation | `target` | `preconditions` | `effects`（上限） | `postconditions` | `partial` | `recovery` |
|---|---|---|---|---|---|---|
| `git.fetch` | 明示 remote と refspec | remote が到達可能 | remote-tracking ref 集合と `FETCH_HEAD` の更新 | 更新後の ref 集合と鮮度証跡 | ref 集合の一部更新 | `REC-FETCH` |
| `git.stage` | explicit pathspec と現在 snapshot | index digest が plan snapshot と一致 | 当該 worktree の index 更新のみ | index digest が予定値と一致 | なし（index は単一 CAS） | `REC-STAGE` |
| `git.commit` | staged snapshot、lint 済 message、expected branch | expected parent / tree と一致 | commit object 1件と branch ref の CAS 更新 | ref が planned OID かつ receipt が存在 | **到達不能**（単一 ref CAS） | `REC-COMMIT` |
| `git.sync` | default / upstream、ahead / behind、dirty | fast-forward 可能 | fetch と `merge --ff-only` | branch が upstream に一致 | fetch 済み・branch 未更新 | `REC-SYNC` |
| `git.publish-branch` | remote、branch、expected HEAD、upstream | remote ref が expected HEAD と一致 | force なし push 1件 | remote ref が expected 値へ更新 | なし | `REC-PUSH` |
| `git.delete-remote-branch` | remote、branch、expected remote SHA、merged evidence | expected remote SHA を再照会して一致 | exact ref 1件の削除のみ | remote ref が存在しない | なし | `REC-PUSH` |

- `evidence` は秘密値を含まない証跡（operation ID、target canonical key、before / after OID、
  fencing token、receipt digest）とする。remote URL・credential・raw stderr を含めない。
- `git.commit` の message は Conventional Commits と任意の WorkUnit / Implements footer を事前検査する。
  stdin 渡しを優先し、file を要する下位 CLI では owner-only の temp 規約（`FLW-DSN-013`）に従う。
- `git.stage` は `git add .` 相当を提供しない。path を明示する。
- `git.delete-remote-branch` は独立 operation とし、finish / merge へ自動連結しない。

### 明示的な非対応

`reset`、`clean`、force push、rebase および公開 branch の履歴書き換え、stash による暗黙退避、
任意 Git subcommand の passthrough、`git config` / remote の add・remove は**提供しない**。
これらは実装しないだけでなく、`next_actions` や診断メッセージで**提案もしない**（`FLW-CON-006`）。

## read operation の共通規律

- 暗黙の fetch や ref 更新を行わない。remote 情報の更新は独立 operation（M1 の `git.fetch`）で行う。
- Git config による pager・color・external diff を無効化して実行する。
- 件数上限で `items` を省略する場合は `shown` / `total` / snapshot 拘束 cursor と
  絞込みの `next_actions` を必ず返す。
- 失敗時は失敗 stage と許可語彙 cause を区別して返す（`references/output-contract.md`）。
