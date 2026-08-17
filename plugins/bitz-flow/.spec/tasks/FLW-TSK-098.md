---
implements: FLW-FR-007, FLW-CON-005
depends_on: FLW-TSK-096
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_cleanup.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py, plugins/bitz-flow/skills/flow-core/schemas/operations, tests/test_flow_m2_runtime.py
status: done
---

### quarantine 解除区分を divergent target ごとに実観測から算出する

- **作業内容**: 現状 `cli.py` は `classify_quarantine` へ `instance_nonce_matches=False` と
  `all_postconditions_match=False` を固定で渡しており、第1条件が常に真になるため
  **到達可能な像が `worktree-unresolved` の1点へ潰れている**。分類ではなく表示である。
  `FLW-DSN-016` §7 の改訂に従い是正する。
  - 分類の単位を集合から **divergent target 個別**へ改める。`data.quarantine.targets[]` の
    各要素が `release_class` を持つ。集合単位の `data.quarantine.release_class` は廃止する。
  - 各入力を実観測から導出する。`chain_valid` は当該 target の chain 検証結果、
    `completed_steps` / `mutation_receipts` は当該 target の receipt、
    `instance_nonce_matches` は receipt の instance nonce と §5 instance identity の再導出の照合、
    `all_postconditions_match` は dir / registry / ref / instance nonce の再照合。
  - 導出できない入力がある target は `release_class: null` と `undetermined_reason` を置き、
    他 target の算出は継続する。`null` と4区分の混在を result 上で区別できる形にする。
  - §7 の `INDETERMINATE` 閉列挙を実装する。store が `chmod 000` で読めない、store が
    ディレクトリでない、store 自体が消えている、chain 検証が破れた、**自 operation の
    未完了痕跡が残る**（intent record が `PENDING_INTENT` / `MUTATING` / `RECONCILING` /
    `PARTIAL`）のいずれかは外部起因と分類せず `INDETERMINATE` を返す。
  - compact 表示は最も重い区分と target 件数を示す。
- **範囲外**: 承認モードの判定（後続タスク）。失敗系 result の必須 field（後続タスク）。
- **検証**: **4区分それぞれへ到達する入力**を与えて区分が実際に変わることを陽性対照で示す。
  固定入力を渡した場合に像が1点へ潰れることを検出する陰性対照を置く。到達不能な区分が
  生じたら FAIL とする。`INDETERMINATE` 閉列挙の各行に対応するテストを置き、自 operation の
  中断を外部起因と誤分類しないことを確認する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
