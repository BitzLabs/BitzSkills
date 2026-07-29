---
id: FLW-NFR-004
version: 1.0
status: draft
domain: tooling
priority: high
origin: FLW-DSN-013
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-004 3platformのprocessとfile I/O可搬性

- **説明**: Python 3.10+実装でprocess tree収束、bounded output、atomic file updateを3platformに提供する。
- **受入基準 (EARS)**:
  - WHEN read operationを開始する THEN bitz-flowは1秒以上300秒以下のaction deadlineを適用すること SHALL
  - WHEN write operationを開始する THEN bitz-flowは10秒以上300秒以下のdeadlineをexecution最大60%、termination最大10%、reconciliation最低30%へ分配すること SHALL
  - WHEN subprocessがtimeoutする THEN bitz-flowはPOSIX process groupまたはWindows Job Objectの子孫を終了してwaitすること SHALL
  - WHEN stdoutまたはstderrがoperation別byte上限を超える THEN bitz-flowはprocess treeを終了して`UNAVAILABLE`を返すこと SHALL
  - WHEN 永続fileを更新する THEN bitz-flowはlstat identity、owner-only temp、file fsync、parse/digest、atomic replace、directory fsync、最終parseを順に実行すること SHALL
  - WHEN filesystemまたはplatformがprocess tree収束かatomicityを保証できない THEN bitz-flowは該当write operationを`UNSUPPORTED`にすること SHALL
  - WHEN Linux、macOS、Windowsのplatform fixtureを実行する THEN bitz-flowはprocess残存0件、原本破損0件、秘密temp path公開0件を記録すること SHALL
- **検証手段**: Linux、macOS、Windowsのprocess、timeout、output overflow、symlink、hardlink、crash、replace fixtureをunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-DSN-004/013とPython 3固定裁定からdraft起票
