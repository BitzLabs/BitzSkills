---
implements: FLW-NFR-011
depends_on: [FLW-TSK-047]
boundary: evals/flow-core/m1-eval/ledger.py, tests/test_flow_m1_ledger.py
status: pending
---

### evidence ledgerの合成とcandidate選択

- **作業内容**: `evals/flow-core/m1-eval/ledger.py` に正本台帳の合成を実装する。

  - **双方向照合**: platform 部分台帳と正本を突き合わせ、**未取込 lease・重複 ID・欠番・
    chain 破損**のいずれかで Gate を `blocked` にする。
  - **candidate 選択**: immutable な `evaluation_objective_id` ごとの**最初の適格 attempt**を
    Gate candidate に固定する。**compatibility key や epoch の変更だけで失敗履歴をリセットしない**。
  - **retry は1回だけ**: 事前拘束した instrument / environment failure code に一致し、
    かつ**被測定物 event が 0 件**の場合だけ、単回 `retry_slot_nonce` を消費して
    `retry_of` 付きの後継を**最大1件**発行する。被測定物 event が1件以上・unknown・
    複数 failure 軸の競合は再試行不可。**元 attempt を無効化せず併記**する。
  - **crash と partition**: 終了 entry の無い attempt は `UNKNOWN` を追記する（既存 entry は
    書き換えない）。partition 中の runner は署名済み local result を隔離保存するだけで
    正本 status を変えない。lease 満了で `UNKNOWN` を追記し、復旧後の PASS/FAIL は
    `late-evidence` として追記するが **candidate を置換しない**。
  - **FAIL 後の再実行**: 新しい confirmation epoch と compatibility key を要求し、
    **同じ Gate で旧 FAIL を PASS へ置換しない**。
  - failure 分類の訂正は**旧 entry を上書きせず訂正 entry を追記**する。

- **完了条件**: 単体テストが PASS し、次の負の対照が拒否されること —
  未取込 lease・重複 ID・欠番・chain 破損での合成、key/epoch 変更だけでの失敗履歴リセット、
  被測定物 event がある attempt の再試行、後継の2件目発行、late-evidence による candidate 置換、
  同一 Gate での FAIL → PASS 置換、既存 entry の上書き。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: 台帳の永続化そのものは durable store（append-only・hash-chain・RPO 0）に委ね、
  ここでは**合成と選択の意味論**を担当する。
