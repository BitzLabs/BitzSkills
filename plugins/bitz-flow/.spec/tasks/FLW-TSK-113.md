---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106,FLW-TSK-111,FLW-TSK-112]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_promotion.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/promotion-state-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/promotion-receipt-v2.schema.json,tests/test_flow_m2_promotion.py,tests/test_flow_m2_contract_v2.py
status: done
---

### owner-only stagingとatomic bundle promotionを実装する

- **作業内容**: exclusive local promotion lock下でactive operation 0件を確認し、code-owned member一覧から
  owner-only stagingへbundleを構築・検証してcurrent pointerをatomic publishする。
  - 通常applyが同じlock下で登録するdurable active operation markerを照合し、1件でもあれば停止する。
  - active公開直前にcurrent generation、runtime identity、bundle digestを再照合する。
  - 未知artifact child probe、署名baseline、registry CAS、schema別activationを実装しない。
  - Git mutationを起動しない。
- **完了条件**: 正常promotion、member欠落、codec不一致、同時promotion、runtime/bundle差替え、
  active operation存在、0件確認直後のapply開始競合、全crash pointで部分activeを残さない。
- **見積り**: FLW-TSK-112と実装PR 4へまとめ、2 sessionを上限とする。
- **実行判定**: minimum-runtime gate完了後に開始し、local critical sectionを越える要求はscope裁定へ戻す。
