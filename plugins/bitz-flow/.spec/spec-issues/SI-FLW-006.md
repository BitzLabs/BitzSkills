---
id: SI-FLW-006
raised_by: M0 TSK-006 process runner の実装（2026-07-31）
target: 観測できなかった事象（byte 上限超過・分類不能な失敗）に対応する cause が診断 cause の許可語彙に存在しない
proposed_change_type: modify
status: open
---
- **目的**: `FLW-DSN-013` の process runner は「stdout / stderr は operation 別 byte 上限まで
  memory へ読み、超過時は process を終了して `UNAVAILABLE`」と定める。しかし
  `FLW-DSN-005` の診断 cause 許可語彙14種に、**出力が上限を超えて全量を観測できなかった**
  ことを表す cause が無い。

  ```text
  not-repository  invalid-ref  invalid-path  dirty  detached-head  no-upstream
  non-fast-forward  conflict  timeout  command-unavailable  permission-denied
  snapshot-mismatch  remote-unavailable  result-indeterminate
  ```

  `FLW-FR-004` は「Git command、parse、timeout、path 検証のいずれかが失敗する THEN
  失敗 stage と許可語彙 cause を区別して返すこと」を要求し、`references/output-contract.md` も
  「失敗時は cause と stage を返す」と規定している。上限超過だけ対応する語彙が無いため、
  要件を満たす cause を選べない。

  M0 の実装（`flowlib/process.py`）では、語彙の追加が公開契約の変更にあたるため独断で増やさず、
  暫定的に次の割り当てを採った。

  | 事象 | code | cause | exit_category |
  |---|---|---|---|
  | timeout | `UNAVAILABLE` | `timeout` | `timeout` |
  | byte 上限超過 | `UNAVAILABLE` | `result-indeterminate` | `output-limit` |
  | command 不在 | `UNAVAILABLE` | `command-unavailable` | `not-found` |

  この暫定割り当てには次の問題がある。

  1. `result-indeterminate` は `FLW-DSN-003` の終了コード表で `INDETERMINATE`（exit 9、
     **副作用の成否**を一意に判定できない状態）と語が対応する。read operation の
     出力打ち切りに同じ語を使うと、write の reconcile が必要な状態と読み分けられない。
  2. 区別が `exit_category`（内部値）にしか無く、公開 result の `data.cause` からは
     「上限超過だったのか、副作用の成否が不明なのか」を判別できない。
  3. 同じ判断が TSK-008（Git read adapter）と TSK-009（dispatcher）でも必要になり、
     暫定のまま M1 以降へ波及する。

  **同種の穴（2026-07-31 追記、TSK-008 実装時）**: 許可語彙には「**どれにも分類できない
  下位コマンド失敗**」を表す cause も無い。Git は既知の失敗（not a git repository、
  unknown revision、pathspec 等）以外にも、環境依存の理由で非ゼロ終了しうる。

  `git_read.py` の `_classify()` は stderr を許可語彙へ正規化するが、既知パターンに
  当たらない場合に返す語が無い。初期実装は fallback を `not-repository` にしていたため、
  **無関係な失敗をリポジトリ不在と偽って報告する**状態になっていた。これは
  「下位 Git / gh の終了コードやメッセージをそのまま公開せず許可語彙へ正規化する」
  という原則を守ろうとして、逆に**誤った事実**を返す典型である。

  暫定対応として fallback を `result-indeterminate` へ変更した（誤った具体 cause より
  安全側）。ただし byte 上限超過と同じ語へ集約されるため、公開 result からは
  「上限超過」「分類不能な失敗」「副作用の成否不明」の3つが区別できない。

- **提案する修正**:
  1. 診断 cause の許可語彙へ **`output-limit-exceeded`**（出力が上限を超え全量を観測できなかった）
     と **`unclassified-failure`**（下位コマンドが失敗したが既知の分類に当たらない）を追加し、
     `FLW-DSN-005` の診断 cause 節と `flow-core/references/output-contract.md`、
     `schemas/result-v1.schema.json` の `$defs.cause` enum を同時に更新する。
     語の名前は裁定時に確定してよい（`unclassified` / `unknown-failure` 等の代案あり）。
  2. `FLW-DSN-013` の process runner 節へ、上限超過時の code（`UNAVAILABLE`）と cause の
     対応を明記する（現状は code だけが書かれている）。
  3. 代案として `result-indeterminate` の定義を「全量を観測できていない」まで広げる案も
     ありうるが、`INDETERMINATE` との語の衝突が残るため推奨しない。3事象
     （上限超過・分類不能・副作用の成否不明）が同じ語へ集約され、公開 result から
     区別できない状態が固定化する。
  4. 語彙は公開契約であるため、追加を M0 の変更セットで行うか、加算のみの変更として
     M1 の入口で行うかを裁定する。
  5. `unclassified-failure` を導入する場合、**それが返された頻度を観測する導線**
     （warning への記録など）を併せて決める。分類漏れが恒久化すると、許可語彙による
     正規化が「実質すべて unclassified」に劣化するため。

- **対象ファイル**: `.spec/design/FLW-DSN-005.md`（診断 cause）、
  `.spec/design/FLW-DSN-013.md`（process runner）、
  `skills/flow-core/references/output-contract.md`、
  `skills/flow-core/schemas/result-v1.schema.json`、
  `skills/flow-core/scripts/flowlib/process.py`（上限超過の暫定割り当ての解消）、
  `skills/flow-core/scripts/flowlib/git_read.py`（`_classify()` の fallback の解消）。

- **確認観点**:
  - 重複: 既存の spec-issue に cause 語彙を扱うものは無い。`SI-FLW-002`〜`005` は
    いずれも accepted 済みで対象が異なる。
  - 既存要件との関係: `FLW-FR-004`（許可語彙 cause の返却）と `FLW-CON-002`
    （Operation Contract）に触れる。両要件は implementing であり EARS 節は書き換え不可のため、
    **要件の変更ではなく語彙表の加算**として扱えるかを裁定する。加算であれば要件の
    受入基準は変わらない（「許可語彙 cause を返す」という条文は語彙の中身に依存しない）。
  - ガードレール: cause は公開契約であり、下位 Git / gh のメッセージをそのまま公開しない
    という原則を崩さないこと。語彙を無制限に増やさず、operation 横断で意味が一意に定まる
    語だけを追加する。
  - 検証: 上限超過 fixture が `UNAVAILABLE` + 新 cause を返すこと、既知パターンに
    当たらない Git 失敗 fixture が `unclassified-failure` を返すこと（既知パターンの
    誤検出で他の cause にならないこと）、既存 cause の意味と重複しないこと、
    schema enum・reference 表・実装定数の三者が一致すること
    （`release_check.py` のマーカー照合と同じ方式を使えるか評価する）。
  - 軽量レーン適否: **不適**（cause 語彙は `flow-core` の公開 result 契約）。

- **影響推定・ロールバック**: 語彙の加算は result schema の `$defs.cause` enum 拡張であり、
  key 集合の変更ではないため schema major を上げない。既存 cause を返していた経路の
  挙動は変わらない。revert は enum と表と定数を戻すだけで完結する。

- **依存**: TSK-005（公開結果契約の凍結）完了済み。TSK-008 / TSK-009 が同じ判断を必要とするため、
  M0 完了前に裁定できると暫定割り当ての波及を止められる。裁定が遅れる場合、M0 は現行の
  暫定割り当てのまま進め、裁定後に1箇所（`process.py` の定数と schema enum）を差し替える。

- **予備判定（推薦）**: **accept 推奨（提案1 と提案2）**。`INDETERMINATE` は副作用の成否が
  不明な状態を表す語として `FLW-DSN-012` / `FLW-DSN-013` の recovery 設計全体で使われており、
  read の出力打ち切りや分類漏れに流用すると recovery matrix の読み分けが濁る。語彙の加算は
  schema major を上げずに済み、影響範囲も小さい。

  `unclassified-failure` の追加（提案1 の後半）は、語彙を増やすこと自体が目的ではなく、
  **誤った具体 cause を返さないための逃げ場**を用意するものである。初期実装が分類漏れの
  fallback に `not-repository` を使い、無関係な失敗をリポジトリ不在と偽って報告していた
  事実が、逃げ場の不在が誤報を生むことを示している。提案5（頻度の観測導線）を伴わない
  導入には反対する。
