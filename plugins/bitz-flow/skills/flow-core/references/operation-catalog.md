# Operation Catalog

公開 operation の contract。**この表にない operation は `UNSUPPORTED`**（exit 8）を返して停止し、
生の `git` / `gh` コマンドを代替案として提示しない。

現在公開されているのは M0 の read-only 3 operation だけである。M1 以降の operation は
実装と fault fixture が揃った milestone で追加する（設計上の配分は `FLW-DSN-012` が正）。

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

## read operation の共通規律

- 暗黙の fetch や ref 更新を行わない。remote 情報の更新は独立 operation（M1 の `git.fetch`）で行う。
- Git config による pager・color・external diff を無効化して実行する。
- 件数上限で `items` を省略する場合は `shown` / `total` / snapshot 拘束 cursor と
  絞込みの `next_actions` を必ず返す。
- 失敗時は失敗 stage と許可語彙 cause を区別して返す（`references/output-contract.md`）。
