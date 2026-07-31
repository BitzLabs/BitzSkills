---
id: FLW-NFR-004
version: 1.1
status: approved
domain: tooling
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-004 3platformのprocess実行可搬性

- **説明**: Python 3.10+標準ライブラリで、deadline、bounded output、process tree収束をLinux、macOS、Windowsに提供する。
- **受入基準 (EARS)**:
  - WHEN subprocess commandを構成する THEN bitz-flowはargument arrayと`shell=False`を使用すること SHALL
  - WHEN read operationを開始する THEN bitz-flowは1秒以上300秒以下のaction deadlineを適用すること SHALL
  - WHEN write operationを開始する THEN bitz-flowは10秒以上300秒以下のdeadlineをexecution最大60%、termination最大10%、reconciliation最低30%へ分配すること SHALL
  - WHEN subprocessがtimeoutする THEN bitz-flowはPOSIX process groupまたはWindows Job Objectの全子孫へ終了要求し、grace経過後の残存processを強制終了してwaitすること SHALL
  - WHEN stdoutまたはstderrがoperation別byte上限を超える THEN bitz-flowはprocess treeを終了して`UNAVAILABLE`を返すこと SHALL
  - WHEN write subprocessをtimeoutまたはoutput overflowで終了する THEN bitz-flowはreconciliation reserve内でoperation固有postconditionを照会すること SHALL
  - WHEN platformで子孫processを所有して収束できない THEN bitz-flowは該当write operationを`UNSUPPORTED`にすること SHALL
  - WHEN Linux、macOS、Windowsのprocess fixtureを実行する THEN bitz-flowはdeadline超過後のprocess残存0件、byte上限超過後のprocess残存0件、shell経由実行0件を記録すること SHALL
- **検証手段**: Linux、macOS、Windowsの正常終了、timeout、grace超過、孫process、output overflow、postcondition reserve、未対応capabilityをunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-DSN-004/013とPython 3固定裁定からdraft起票
  - 1.1 (2026-07-29) draftレビューでatomic file I/OをFLW-NFR-007へ分離し、process実行可搬性へ限定
