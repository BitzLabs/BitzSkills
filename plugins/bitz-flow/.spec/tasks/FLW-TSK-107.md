---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_approval_binding.py,tests/test_flow_m2_approval_binding.py
status: pending
---

### approval-mode宣言をHEAD・index・worktreeへ束縛する

- **作業内容**: repository rootから`.bitz-flow/approval-mode.json`をcomponent単位の非追随walkで読み、
  HEAD・index・worktreeの三者状態を`absent` / `bound` / `invalid`へ分類する。
  - 三者すべて不在の場合だけ`absent`とする。
  - regular file、実効OS principal所有、group/world非書込み、HEAD追跡済み、三者blob一致を満たす
    場合だけ`bound`とする。
  - symlink/reparse point、staged-only、未追跡、staged deletion、worktree deletion、読取中置換を
    `invalid`として`BLOCKED`にする。
  - repository identityとplatform file identityを含むcanonical binding digestを返す。
- **完了条件**: Linux・macOS・Windows adapter fixtureで正常なbound/absentを受理し、各invalid形を
  誤ってabsentへ降格させず、決定的な差替えhookで読取競合を検出する。
- **実行判定**: filesystem/Git境界の難実装。上位相談先が利用不能なため設計書を正として自己実行し、
  platform差異が設計matrixを越える場合は実装を止める。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
