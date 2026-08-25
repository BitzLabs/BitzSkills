---
implements: FLW-NFR-014
depends_on: [FLW-TSK-131]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_operability.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,tests/test_flow_m2_judgement_quality.py,tests/test_flow_m2_operability.py,evals/flow-core/m2-eval/run_local_confirmation.py
status: implementing
---

### 判定APIの矛盾を解消し網が隠す内部障害を観測可能にする

`FLW-REV-029:GP-005`（`SYN-006` / `SYN-007`）。

- **実測した欠陥**:
  - `SYN-006`（audit。**再現した**）: `audit_operation`は`INDETERMINATE`以外をすべて
    `OK`（exit 0）にし、その**全部**に`create-reconcile-plan`を促していた。
    `confirmed-complete`（何もしなくてよい）へreconcileを促し、`quarantine`と
    `confirmed-incomplete`（復旧を要する）を`OK`と表示していた。
    **運用者は隔離された操作を正常と誤認する。**
  - `SYN-007`: dispatcherの網が例外を一律`UNAVAILABLE`へ変換し、種別も発生箇所も
    残さなかった。実際にこの網が`FLW-TSK-116`／`117`のhandler欠陥
    （`recovery_class`欠落によるValueError）を隠していた。
- **再現しなかった指摘**: `SYN-006`のうち「`verify_receipt`がreceiptsを見ていない」。
  `transaction.inspect()`がreceipt chain（同梱緊急receiptのbinding・supersede関係・
  terminal eventとの結合）を検証して`problems`へ畳み込んでおり、`healthy`はその結果である。
  receiptを削除・破損させると判定は実際に反転する（実測）。
  **一度は指摘どおり`_receipt_chain_problems()`を実装したが、実経路で一度も発火せず、
  発火するときは`state`が`INDETERMINATE`へ潰れているため誤った理由を出すだけだったので
  撤去した。** 指摘はsourceの見た目に基づくもので、振る舞いとしては成立していない。
- **作業内容**:
  - 分類→operator actionの写像を1か所（`_AUDIT_ACTIONS`）へ寄せ、復旧を要する分類
    （`_CLASSIFICATIONS_NEEDING_RECOVERY`）を`OK`にしない。
  - `verify_receipt`の判定は`inspect()`へ一本化し、`receipt_count`をdetailsへ出す。
  - 網が受け止めた例外を**内部向けにだけ**記録する（`LAST_UNEXPECTED_FAILURE`と、
    `BITZ_FLOW_INTERNAL_LOG`が指す場合のみ1行JSON追記）。公開resultは変えない。
  - `tests/test_flow_m2_operability.py`が旧契約（`confirmed-incomplete`でexit 0）を
    固定していたため、是正後の契約へ改める。
- **完了条件**:
  - `OK`扱いになる分類が`confirmed-complete`だけであること。
  - codeとoperator actionが全分類で矛盾しないこと。
  - receiptの削除・破損で判定が反転すること（陽性対照）。
  - 網が受け止めた例外の種別と発生箇所が内部から観測でき、かつ公開resultへ漏れないこと。
- **実行判定**: `GP-006`に従い、source照合ではなく**実際に壊して振る舞いを見る**。
  3変異（旧audit写像の復元・記録呼び出しの除去・内部情報の公開result混入）で
  それぞれ6件／3件／1件が検出されることを確認した。
