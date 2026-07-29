---
id: FLW-CON-004
version: 1.0
status: draft
domain: governance
priority: high
origin: FLW-REV-002
verification_method: benchmark
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-CON-004 cross-host createの単一coordinator境界

- **説明**: 分散lockを実装せず、別hostまたは別cloneから競合し得るGitHub createを単一coordinator運用と安全側縮退で統制する。
- **受入基準 (EARS)**:
  - WHEN GitHub createが別hostまたは別cloneから同じWorkUnitへ実行され得る THEN bitz-flowはplanへcoordinator identity、WorkUnit割当、cross-host排他を内部では保証しないことを表示すること SHALL
  - WHEN 同じWorkUnitを単一coordinatorだけへ割り当てたことを証明できない THEN bitz-flowは該当create operationを`UNSUPPORTED`にすること SHALL
  - WHEN idempotency markerを使用する THEN bitz-flowは当該markerをcross-host lockまたはcoordinator所有権の証明として扱わないこと SHALL
  - WHEN coordinator重複割当または同じmarkerの複数副作用を検出する THEN bitz-flowは`BLOCKED`を返し、対象を自動close、delete、またはeditしないこと SHALL
  - WHEN M3またはM4のcanaryを実行する THEN bitz-flowはWorkUnitごとのcoordinator重複割当0件とmarker重複0件を記録すること SHALL
  - WHEN canaryでcoordinator重複割当またはmarker重複を1件以上検出する THEN bitz-flowは当該milestoneのPromotion Gateを`BLOCKED`にすること SHALL
- **検証閾値**: coordinator重複割当0件、marker重複0件。1件でも検出した場合はPromotion Gateを停止する。
- **検証手段**: 2つのhostまたはcloneを模擬した競合fixtureとM3/M4 canary manifestを用い、plan表示、UNSUPPORTED縮退、重複検出、Promotion Gate停止をbenchmarkで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-NFR-003とFLW-REV-002 SYN-101からcross-host運用境界を分離してdraft起票
