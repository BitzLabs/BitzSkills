---
id: FLW-NFR-006
version: 1.0
status: draft
domain: execution
priority: high
origin: FLW-DSN-012
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-006 同一host writeの直列化

- **説明**: 同じtargetを変更する同一host上のprocessをper-target OS advisory lockで直列化する。
- **受入基準 (EARS)**:
  - WHEN write operationを登録する THEN bitz-flowはrepo identity、operation family、canonical targetから安定`concurrency_key`を導出すること SHALL
  - WHEN write operationをapplyする THEN bitz-flowはprecondition再照会より前に`concurrency_key`のOS advisory lockを取得し、postconditionまたはreconcile完了まで保持すること SHALL
  - WHEN 同じ`concurrency_key`を持つ複数processが同一hostでwriteを要求する THEN bitz-flowは同時にmutation区間へ入るprocessを最大1件にすること SHALL
  - WHEN lockをbounded wait内に取得できない THEN bitz-flowは副作用を実行せず`BLOCKED`を返すこと SHALL
  - WHEN platformまたはfilesystemでprocess終了時に解放される安全なadvisory lockを提供できない THEN bitz-flowは該当write operationを`UNSUPPORTED`にすること SHALL
  - WHEN staleなlock fileだけが存在する THEN bitz-flowはfileの存在を所有証明として扱わずOS lockの取得結果で判定すること SHALL
  - WHEN 同一keyと異なるkeyの並行fixtureを実行する THEN bitz-flowは同一keyの最大同時mutation数1件、lock待機中の副作用0件、異なるkeyの誤block 0件を記録すること SHALL
- **検証手段**: 複数process、lock競合、bounded wait、process異常終了、stale lock file、異なるkeyを模擬するunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-NFR-003から同一hostのwrite直列化を分離してdraft起票
