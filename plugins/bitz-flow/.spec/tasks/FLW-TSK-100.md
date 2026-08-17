---
implements: FLW-FR-013
depends_on: FLW-TSK-096, FLW-TSK-098, FLW-TSK-099
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/result.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/references/output-contract.md, tests/test_flow_m2_runtime.py, tests/test_flow_result_contract.py
status: done
---

### 非 ok の result に cause / recovery_class / next_actions を必須化する

- **作業内容**: recovery matrix は文書にあるが公開 result へ載っていない。`worktree.*` の
  write 失敗系は `summary` と `stage` だけを持ち、`cause` も `recovery_class` も
  `next_actions` も空である。`FLW-REV-018` の是正で新設した fail-closed の `BLOCKED` も
  同じ穴を継いでいる。`FLW-DSN-016` §8 の改訂に従い是正する。
  - `build_result` に検査を置き、**非 ok の result が上記3 field を欠く場合は組み立て時に拒否**する。
    operation 個別のテストで担保する方式は、新しい失敗経路を足すたびに同じ穴が再発する。
  - `recovery_class` は `recovery_for(code, cause)` から決定する。matrix を引かずに置かない。
  - `human-stop` に限り `next_actions` を空にでき、その場合 `data.required_human_input` を必須にする。
    空であること自体が matrix から導かれた結論でなければならない。
  - 対象は `worktree.*` の失敗系すべて。入力欠落（`INVALID_INPUT`）、plan 失敗（`BLOCKED`）、
    承認不足（`APPROVAL_REQUIRED`）、apply 中の例外（`BLOCKED`）、承認モード宣言と registry の
    不整合による `BLOCKED`、§7 の `INDETERMINATE`。
  - `output-contract.md` へ非 ok result の必須 field を明記する。
- **範囲外**: 分類ロジックそのもの（先行タスク）。
- **検証**: 全失敗経路を列挙したテーブル駆動テストで、各経路の result が3 field を持つことを
  検査する。`recovery_class` を欠いた result を組み立てようとしたら例外になることを陰性対照で示す。
  `human-stop` の空 NEXT と、matrix を引かずに省略した空欄が区別されることを確認する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
