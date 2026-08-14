---
implements: FLW-CON-002
depends_on: [FLW-TSK-058]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/consistency-exceptions.json, tests/test_m2_spec_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-059.md
status: done
---

### quarantine解除を証跡軸へ変更

- **作業内容**: SI-FLW-047の裁定に従い、instance nonceをdiscard後も残る領域へ移し、intent/nonce/receiptで中断状態を4区分へ一意化する。stepをverify/mutateへ型分けする。
- **検証**: 4区分、証跡、nonce保存先、mutating step全射規約、独立operationへの責務分離を機械検証する。
