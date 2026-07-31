# Output Contract

`flow.py` が返す result の公開契約。`--format compact`（既定）と `--format json` は
**同じ判定**（`ok` / `code` / `exit_code`）を返す。schema の正は `schemas/result-v1.schema.json`。

## 出力してはならないもの

raw command、stdout、stderr、environment、credential、temp path、exception、traceback。
result envelope は `additionalProperties: false` でこれを機械的に禁止する。

## compact renderer

固定 token・固定 field 順・1項目1行。0件 field と null は省略する。

```text
OK git.status snapshot=sha256:ab12 branch=feat/x changed=2 ahead=1 behind=0
 M src/a.py
?? tests/test_a.py
NEXT git.diff-summary snapshot=sha256:ab12
```

行の種類と順序は次に固定する。

| 順 | 行 | 形式 |
|---:|---|---|
| 1 | 判定行 | `<CODE> <operation> [cause=<cause>] [snapshot=<sha>] <operation 別の要約 token>` |
| 2 | blocking / error 項目 | 1件1行 |
| 3 | 変更対象 | 1件1行 |
| 4 | 通常項目 | 1件1行 |
| 5 | truncation 行 | `TRUNCATED shown=<n> total=<m> cursor=<snapshot-bound>` |
| 6 | next action | `NEXT <domain>.<action> <key>=<value> ...` |

- blocking / error を最優先し、次に変更対象、通常項目の順で描画する。
- 上限超過で項目を省略したときは truncation 行と絞込みの `NEXT` を**必ず**返す。
- mutation の判断に全件確認が必要なのに上限超過した場合、apply を `BLOCKED` にする（M1 以降）。
- `NEXT` は許可された domain / action と必要引数だけを出す。shell 文字列や生コマンドを出さない。
- path は repo 相対表示を既定とし、repo 外 target だけ canonical absolute path を出す。

## 終了コードと code

| exit | code | 意味 |
|---:|---|---|
| 0 | `OK` / `READY` / `DONE` | 正常 |
| 2 | `INVALID_INPUT` | 引数・schema・ref・path が不正 |
| 3 | `BLOCKED` | 前提、policy、CI、依存で続行不可 |
| 4 | `APPROVAL_REQUIRED` | plan 済みで必要な外部裁定待ち |
| 5 | `UNAVAILABLE` | Git / gh / auth / network / timeout 等が利用不能 |
| 6 | `STALE` | snapshot / head / remote が plan 時点から変化 |
| 7 | `PARTIAL` | 一部副作用が完了。外部状態から再開可能 |
| 8 | `UNSUPPORTED` | capability または操作が未対応 |
| 9 | `INDETERMINATE` | 副作用の成否を一意に判定できず reconcile が必要 |

`ok` は `exit_code == 0` と一致する。下位 Git / gh の終了コードはそのまま公開せず、
`data.cause` の許可語彙へ正規化する。

M0（read-only）で到達し得るのは 0 / 2 / 3 / 5 / 6 / 8 だけである。
4 / 7 / 9 は write operation を導入する M1 以降で使う。

## `data.cause` の許可語彙

```text
not-repository     invalid-ref        invalid-path       dirty
detached-head      no-upstream        non-fast-forward   conflict
timeout            command-unavailable permission-denied snapshot-mismatch
remote-unavailable result-indeterminate
```

失敗時は cause に加えて失敗 stage（`inspect` / `parse` / `validate` / `plan` / `apply` /
`post-check`）を返し、どの工程で落ちたかを区別できるようにする。

## snapshot と cursor

- `snapshot` は operation が観測した事実の canonical bytes から計算する fingerprint。
- `cursor` は `snapshot` へ拘束する。呼出時の snapshot と再計算値が違えば `STALE`（exit 6）。
- 初期版は raw 出力の cache を持たない。working tree が変わった場合は古い結果を復元せず再取得する。

## `result_digest`

`result_digest` key **自身を除く** result object を、UTF-8・key 辞書順・余分な空白なし・
schema が許可した整数表現へ正規化した byte 列の SHA-256。

- 呼出側は 1 invocation の完全な JSON result を 1 保存単位とし、利用前に digest を再計算する。
- 部分抜粋は監査原本として扱わない。
- 保存・転送時の破損と不一致を検出するためのもので、result と digest を同時に変更できる主体に
  対する耐改ざん性は保証しない。必要なら呼出側が署名または追記専用 storage を用意する。

## 互換性

key 集合は**加算のみ**。既存 key の意味を変える場合は schema major を上げる
（`bitz-flow/result/v1` → `v2`）。`data` は operation 別 schema が必須 field・型・enum・
cardinality を定め、未知 field を許容するが既存 field の意味を変えない。
