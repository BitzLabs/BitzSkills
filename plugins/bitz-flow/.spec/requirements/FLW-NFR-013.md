---
id: FLW-NFR-013
version: 1.0
status: deprecated
domain: safety
priority: high
origin: SI-FLW-077
verification_method: unit-test
derived_from: FLW-NFR-011
supersedes:
superseded_by: FLW-NFR-014
confidence: high
---

### FLW-NFR-013 approval-mode 宣言の完全性と plan/apply 束縛

- **説明**: 配備意図を示す `approval-mode.json` を検証可能な宣言として扱い、plan時に
  確認した承認強度がapply時・各mutation時まで低下しないよう束縛する。
- **受入基準 (EARS)**:
  - WHEN bitz-flowが`approval-mode.json`を評価する THEN regular file、実行者所有、
    group/world非書込み、Git index追跡済み、indexとworktreeの内容一致をすべて満たす
    宣言だけを`bound`とし、path不在だけを`absent`とし、symlink、非通常file、未追跡、
    所有・権限不正、内容不一致または読取競合を`invalid`として`BLOCKED`にすること SHALL
  - WHEN `bound`または`absent`の宣言からOperationPlanを作成する THEN bitz-flowは
    repository identity、宣言状態、mode、index blob、worktree content digest、file identityを
    正規化した`approval_declaration_digest`をsnapshotおよびoperation identityへ固定すること SHALL
  - WHEN signed-capabilityを検証する THEN bitz-flowは`approval_declaration_digest`を
    capability contextの署名対象に含め、digestが異なるcapabilityを受理しないこと SHALL
  - WHEN applyの承認検証後または各mutation直前に宣言を再評価する THEN bitz-flowは
    plan時の`approval_declaration_digest`と不一致、宣言の新規作成・削除・内容変更・inode置換を
    `STALE`または`BLOCKED`として停止し、その再照合点以後のGit副作用を0件にすること SHALL
  - WHEN plan時から宣言が`absent`のまま継続する THEN bitz-flowは既存の`plan-digest`承認を
    利用できるが、途中で宣言状態またはdigestが変化した場合は自動再applyしないこと SHALL
- **検証手段**: unit testで、追跡済み不変宣言のsigned-capability／宣言なしのplan-digestの
  正常系、symlink・directory・未追跡・権限不正・index/worktree不一致の拒否、plan後および
  mutation間の作成・削除・置換・内容変更時の副作用0件を検証する。
- **Revision History**:
  - 1.0 (2026-08-22) `SI-FLW-077`を受けた初版（draft起票）
