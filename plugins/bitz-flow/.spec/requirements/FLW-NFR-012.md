---
id: FLW-NFR-012
version: 1.0
status: approved
domain: safety
priority: high
origin: FLW-REV-009
verification_method: unit-test
derived_from: FLW-NFR-006
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-012 cross-family writeのtarget guard直列化

- **説明**: operation familyが異なっても同じmutation targetを変更するwriteを、共通target guardで直列化する。
- **受入基準 (EARS)**:
  - WHEN write operationをapplyする THEN bitz-flowはfamily別lockより先に`repo identity × canonical mutation target`から導出したtarget guardを取得すること SHALL
  - WHEN target guardを保持する THEN bitz-flowはpending intention/quarantineの検査、作成、mutation、postcondition/reconcile、解除まで同じguardを保持すること SHALL
  - WHEN異なるoperation familyが同じtargetへ並行writeする THEN bitz-flowは同時mutationを最大1件とし、pending検出後の副作用を0件にすること SHALL
  - WHEN operationが複数targetを変更する THEN bitz-flowはcanonical keyの昇順で全guardを取得し、逆順取得を拒否すること SHALL
  - WHEN安全にguardを取得できない THEN bitz-flowは副作用を実行せず`UNSUPPORTED`または`BLOCKED`を返すこと SHALL
- **検証手段**: stage/commit、sync/push等のcross-family並行、複数target逆順、pending存在、process crashをunit fault fixtureで検証する。
- **Revision History**:
  - 1.0 (2026-08-11) FLW-REV-009再レビューのcross-family競合を受けてdraft起票
