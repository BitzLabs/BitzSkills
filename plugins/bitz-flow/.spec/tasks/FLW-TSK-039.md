---
implements: FLW-FR-005
depends_on: [FLW-TSK-038]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/git_write.py, tests/test_flow_m1_git_write.py
status: pending
---

### git.stageのindex CAS（native index.lock規約）

- **作業内容**: `flowlib/git_write.py` に `git.stage` の plan / apply を実装する。
  read adapter（`git_read.py`）に write を混ぜない（read / write の境界が boundary 宣言の単位）。

  - **plan**: 副作用なしで explicit pathspec・現在 snapshot・予定 index bytes を返す。
    `git add .` 相当は提供せず path を明示する。plan が列挙した effects が apply の上限である。
  - **apply の index CAS**: target guard 取得後に Git native `index.lock` を **exclusive create** し、
    lock 保持下で現 index digest を再読して plan snapshot と一致した場合だけ、予定 bytes を
    `index.lock` へ書いて file fsync し、**atomic rename + directory fsync** で公開する。
    **lock 内から通常の `git add` を起動しない**。
  - native index lock / atomic rename / 同一 filesystem を提供できない platform では
    stage を `UNSUPPORTED` とする。
  - 管理外 process が native lock を無視した場合は postcondition 不一致として **quarantine** し、
    その環境を qualification 不適格として報告する。
  - `git_read.py` の共通 flags（pager / color / external diff の無効化）と環境変数、
    cause 正規化の方針を共有する（生の stderr を公開しない）。

- **完了条件**: 実 Git リポジトリを使う単体テストが PASS し、次が確認できること —
  plan が副作用 0 であること、index digest が plan 時点と違えば副作用 0 で `STALE` を返すこと、
  `index.lock` が既に存在する場合に副作用 0 で `BLOCKED` になること、
  apply 後に index digest が予定値と一致すること、`git add .` 相当の API が存在しないこと。
  `M1-FLT-029`（index digest 照合直後に外部 `git add` が割り込む）で native lock により排他され、
  無視する writer が quarantine されること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: **公開 operation を増やさない**（`FLW-DSN-014` 縮退規則3）。dispatcher へ結線せず、
  `git.stage` は引き続き `UNSUPPORTED` を返す。本タスクは内部 adapter の実装と fault 検証にとどめる。
