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
NEXT git.diff-summary base=HEAD
```

行の種類と順序は次に固定する。

| 順 | 行 | 形式 |
|---:|---|---|
| 1 | 判定行 | `<CODE> <operation> [cause=<cause>] [snapshot=<sha>] <operation 別の要約 token>` |
| 2 | blocking / error 項目 | 1件1行 |
| 3 | 変更対象 | 1件1行 |
| 4 | 通常項目 | 1件1行 |
| 5 | truncation 行 | `TRUNCATED shown=<n> total=<m>` |
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

### M1 で新たに到達するコード

write を公開する M1-3 以降、次の3つが到達可能になる。到達した場合の扱いは
`references/recovery-matrix.md` が正で、そこに登録の無い組み合わせは `human-stop` へ fail-closed する。

| exit | code | write での意味 | 自動継続 |
|---:|---|---|---|
| 4 | `APPROVAL_REQUIRED` | plan 済みで、必要な外部裁定（`explicit-human`）を待っている | 不可。人間の承認が要る |
| 7 | `PARTIAL` | 一部副作用が完了し、外部状態から completed / remaining を確定できる | 残 step の自動 apply は禁止。read-only reconcile のみ |
| 9 | `INDETERMINATE` | 副作用の成否を一意に判定できない | mutation 全般を停止し、空 `next_actions` と `required_human_input` を返す |

`git.commit` の `PARTIAL` は**到達不能**である（単一 ref の CAS は原子的で部分完了が無い）。
receipt を欠く場合は `DONE` と推定せず `INDETERMINATE` とする。

write operation が返す `code` は次の7つに限る（`OK` / `READY` / `UNAVAILABLE` は read 側の語彙）。

```text
DONE  PARTIAL  INDETERMINATE  STALE  BLOCKED  INVALID_INPUT  UNSUPPORTED
```

## 状態語彙の namespace 分離

同じ語（`PASS` / `PARTIAL` / `STALE` 等）が別の意味で現れるため、**5つの enum を別 field として持ち、
相互に読み替えない**（`FLW-DSN-015`）。

| namespace | 置き場 | 値 |
|---|---|---|
| `code`（result code） | result envelope | `OK` / `READY` / `DONE` / `INVALID_INPUT` / `BLOCKED` / `APPROVAL_REQUIRED` / `UNAVAILABLE` / `STALE` / `PARTIAL` / `UNSUPPORTED` / `INDETERMINATE` |
| `write_state` | `data.write_state` | `PLANNED` / `GUARDED` / `PENDING_INTENT` / `MUTATING` / `RECONCILING` / `DONE` / `PARTIAL` / `STALE` / `QUARANTINED` |
| `intent_record_state` | intent record | `PENDING` / `RECONCILING` / `PARTIAL` / `STALE` / `QUARANTINED` / `RELEASED` |
| `gate_status` | qualification manifest と Gate 判定 | `PASS` / `FAIL` / `BLOCKED` |
| `attempt_status` | evidence ledger entry | `STARTED` / `PASS` / `FAIL` / `ABORTED` / `UNKNOWN` |

schema の正は `schemas/result-v1.schema.json`（`code` / `write_state`）、
`schemas/intent-record-v1.schema.json`（`intent_record_state`）、
`schemas/evidence-ledger-entry-v1.schema.json`（`attempt_status` / `gate_status`）。

## write operation の出力（M1-3 以降）

write の result は read と同じ envelope を使い、次を追加で持つ。

- `data.write_state` — 状態機械上の位置。read では省略または null。
- `data.guard_targets` — target guard を取得した canonical mutation target。canonical key の昇順。
  raw path を含めない（`index` / `local-ref` / `remote-tracking-ref` / `fetch-head` / `remote-ref` /
  `worktree-dir` / `worktree-registry` の閉集合）。
- `invocation.stage` — `plan` / `apply` / `post-check` を区別する。
- `approval` — `required` が `explicit-human` の場合、`source` と `reference` に裁定の所在を載せる。
  CLI が人間本人を認証したことは表さない。
- `operation_id` — plan と apply を結ぶ安定 ID。apply は plan 時の `operation_id` と `snapshot` の
  一致を要求し、不一致なら**副作用 0 で** `STALE` を返す。quarantine 解除後の mutation には
  新しい `operation_id` を要求する（旧 ID の再利用は拒否）。

compact では判定行に `write_state=` と `stage=` を載せ、変更対象の行に guard target を 1件1行で描画する。
mutation の判断に全件確認が必要なのに項目が上限超過した場合、apply を `BLOCKED` にする。

## `data.cause` の許可語彙

```text
not-repository     invalid-ref        invalid-path       dirty
detached-head      no-upstream        non-fast-forward   conflict
timeout            command-unavailable permission-denied snapshot-mismatch
remote-unavailable result-indeterminate approval-expired
unsupported-approval-mode unsupported-filesystem quarantined
```

値の正は `schemas/result-v1.schema.json` の `$defs/cause`（`FLW-DSN-016` §2 が閉集合の唯一の正）。

失敗時は cause に加えて失敗 stage（`inspect` / `parse` / `validate` / `plan` / `apply` /
`post-check`）を返し、どの工程で落ちたかを区別できるようにする。

## 非ok result の必須 field（`FLW-TSK-100`）

`ok: false`（`exit_code != 0`）の result は、`data.cause` / `data.recovery_class` /
`next_actions` の3つを欠かせない。`build_result` がこれを組み立て時に検査し、
欠けた result は例外で拒否する（operation 個別のテストで担保する方式は、新しい
失敗経路を足すたびに同じ穴が再発するため採らない）。

- **`data.cause`** — 上の許可語彙から選ぶ。**`APPROVAL_REQUIRED` だけ免除**する
  （診断された失敗ではなく、write フローが人間の承認を待つ通常の中断点であり、
  `references/recovery-matrix.md` の決定表もこの code の行を持たないため）。
- **`data.recovery_class`** — `retry-read` / `reconcile-only` / `replan-human` /
  `human-stop` の閉集合（`references/recovery-matrix.md` が正）。
  `worktree_cleanup.recovery_for(code, cause)` から決定し、値を手で書かない。
  未登録の `(code, cause)` は fail-closed に `human-stop` へ倒れる。
- **`next_actions`** — `recovery_class` が `human-stop` の場合に**限り**空にできる。
  その場合 `data.required_human_input` を必須とする。空であること自体が
  recovery matrix から導かれた結論でなければならない。`human-stop` 以外の
  `recovery_class` では `next_actions` を空にできない。

## snapshot

- `snapshot` は operation が観測した事実の canonical bytes から計算する fingerprint。
- **`snapshot` は operation 固有である。** 観測対象が operation ごとに違うため、同一 repo・
  同一時点でも `repo.inspect` / `git.status` / `git.diff-summary` の値は一致しない。
  **別 operation へ引き渡してはならない**（渡せば必ず `snapshot-mismatch` になる）。
- したがって **`NEXT` が `snapshot` を載せるのは「次も同じ operation」のときだけ**である
  （打ち切られた一覧を辿るページング）。operation をまたぐ誘導には載せない。
  楽観ロックを使いたい呼出側は、対象 operation を一度読んでからその operation 自身の
  `snapshot` を渡す。
- 打ち切りは `TRUNCATED shown=<n> total=<m>` で可視化する。**継続位置（cursor）は返さない。**
  受け取る引数が無いため、提示すると呼出側が渡そうとして `INVALID_INPUT` になる。
  残りが要るなら `--limit` を大きくして取り直す。
- `STALE` から回復するときは `--snapshot` を外して同じ operation を呼び直す。
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
