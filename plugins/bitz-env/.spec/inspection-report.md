# inspection-report.md (2026-07-11)

成果物数: 18 / 問題: 0 / 幽霊参照: 2 / 孤児要件: 0

## 問題一覧
- なし ✅

## 幽霊参照（存在しないIDへの参照）
- ENV-TSK-006 ← .spec/tasks/ENV-TSK-008.md, .spec/tasks/ENV-TSK-007.md
- ENV-TSK-009 ← .spec/tasks/ENV-TSK-010.md

## 孤児要件（approved以降なのに implements するタスクがない）
- なし ✅

## テスト/実装からの参照がない要件（approved以降）
- ENV-CON-001
- ENV-CON-002
- ENV-CON-003
- ENV-CON-004
- ENV-FR-001
- ENV-FR-002
- ENV-FR-003
- ENV-FR-004
- ENV-FR-005
- ENV-FR-006
- ENV-FR-007
- ENV-FR-008
- ENV-FR-009
- ENV-FR-010
- ENV-NFR-001
- ENV-NFR-002

## docs 乖離（派生元 docs が派生後に変更された要件 — stale 候補）
※ 乖離は候補提示のみ。stale 付与は references/lifecycle.md の再伝播プロトコル（判定パス→人間確認）を経ること
- なし ✅

## Traceability Matrix
| ID | status | domain | v-method | tasks | 参照元数 |
|----|--------|--------|----------|-------|----------|
| ENV-CON-001 | approved | guardrail | manual-check | 1 | 1 |
| ENV-CON-002 | approved | collab | manual-check | 1 | 2 |
| ENV-CON-003 | approved | deploy | manual-check | 1 | 2 |
| ENV-CON-004 | approved | guardrail | manual-check | 1 | 1 |
| ENV-DSN-001 | approved | deploy |  | 0 | 0 |
| ENV-FR-001 | approved | guardrail | example-test | 2 | 2 |
| ENV-FR-002 | approved | guardrail | example-test | 2 | 2 |
| ENV-FR-003 | approved | deploy | example-test | 1 | 1 |
| ENV-FR-004 | approved | deploy | example-test | 1 | 1 |
| ENV-FR-005 | approved | collab | example-test | 3 | 3 |
| ENV-FR-006 | approved | collab | example-test | 4 | 4 |
| ENV-FR-007 | approved | deploy | example-test | 1 | 1 |
| ENV-FR-008 | approved | guardrail | example-test | 1 | 1 |
| ENV-FR-009 | approved | deploy | example-test | 1 | 1 |
| ENV-FR-010 | approved | deploy | example-test | 2 | 2 |
| ENV-NFR-001 | approved | guardrail | benchmark | 1 | 1 |
| ENV-NFR-002 | approved | guardrail | manual-check | 1 | 1 |
| REV-001 | approved | governance |  | 0 | 0 |

**判定: FAIL ❌（上記を解消するまで verified に進めない）**
