# inspection-report.md (2026-08-07)

成果物数: 53 / 問題: 0 / 幽霊参照: 0 / 実装待ち: 15 / 孤児要件: 0 / 検証証跡: 0

## 問題一覧
- なし ✅

## 幽霊参照（存在しないIDへの参照）
- なし ✅

## 監査 WARN（代行遷移の裁定参照など — FAIL にしない）
- なし ✅

## Gate 通過記録（.spec/gates/ — 人間裁定の検分証跡）
- FLW-GATE-001 — design / 2026-07-29 / 裁定者 hide / 対象 14 件 / 確認した裁定記録 1 件

## 実装待ち要件（approved だが implements するタスクがない — WARN）
- FLW-CON-003
- FLW-CON-004
- FLW-CON-005
- FLW-CON-006
- FLW-FR-005
- FLW-FR-006
- FLW-FR-007
- FLW-FR-008
- FLW-FR-009
- FLW-FR-010
- FLW-FR-011
- FLW-NFR-003
- FLW-NFR-005
- FLW-NFR-006
- FLW-NFR-007

## 孤児要件（implementing以降なのに implements するタスクがない）
- なし ✅

## テスト/実装からの参照がない要件（approved以降）
- FLW-CON-003
- FLW-CON-004
- FLW-CON-005
- FLW-CON-006
- FLW-FR-005
- FLW-FR-006
- FLW-FR-007
- FLW-FR-008
- FLW-FR-009
- FLW-FR-010
- FLW-FR-011
- FLW-FR-012
- FLW-NFR-001
- FLW-NFR-003
- FLW-NFR-004
- FLW-NFR-005
- FLW-NFR-006
- FLW-NFR-007

## 参照がない manual-check 要件（テスト参照は原理的に生じない — 検証記録で担保）
- FLW-CON-001
- FLW-FR-002

## 他ワークスペースのテスト/実装から参照されている要件
- FLW-CON-002 ← BitzSkills/tests/test_flow_contract.py
- FLW-FR-003 ← BitzSkills/tests/test_flow_contract.py
- FLW-FR-004 ← BitzSkills/tests/test_flow_contract.py
- FLW-NFR-008 ← BitzSkills/tests/test_flow_contract.py

## docs 乖離（派生元 docs が派生後に変更された要件 — stale 候補）
※ 乖離は候補提示のみ。stale 付与は references/lifecycle.md の再伝播プロトコル（判定パス→人間確認）を経ること
- なし ✅

## Traceability Matrix
| ID | status | domain | v-method | tasks | 参照元数 |
|----|--------|--------|----------|-------|----------|
| FLW-CON-001 | 実装中（implementing） | governance | manual-check | 2 | 2 |
| FLW-CON-002 | 実装中（implementing） | governance | unit-test | 3 | 3 |
| FLW-CON-003 | 承認済み（approved） | governance | unit-test | 0 | 0 |
| FLW-CON-004 | 承認済み（approved） | governance | benchmark | 0 | 0 |
| FLW-CON-005 | 承認済み（approved） | governance | benchmark | 0 | 0 |
| FLW-CON-006 | 承認済み（approved） | governance | unit-test | 0 | 0 |
| FLW-DSC-000 | 起草中（draft） |  |  | 0 | 0 |
| FLW-DSC-001 | 起草中（draft） |  |  | 0 | 0 |
| FLW-DSC-002 | 起草中（draft） |  |  | 0 | 0 |
| FLW-DSC-003 | 起草中（draft） |  |  | 0 | 0 |
| FLW-DSC-004 | 起草中（draft） |  |  | 0 | 0 |
| FLW-DSC-005 | 起草中（draft） |  |  | 0 | 0 |
| FLW-DSC-006 | 起草中（draft） |  |  | 0 | 0 |
| FLW-DSN-000 | active |  |  | 0 | 0 |
| FLW-DSN-001 | active |  |  | 0 | 0 |
| FLW-DSN-002 | active |  |  | 0 | 0 |
| FLW-DSN-003 | active |  |  | 0 | 5 |
| FLW-DSN-004 | active |  |  | 0 | 4 |
| FLW-DSN-005 | active |  |  | 0 | 5 |
| FLW-DSN-006 | active |  |  | 0 | 0 |
| FLW-DSN-007 | active |  |  | 0 | 0 |
| FLW-DSN-008 | active |  |  | 0 | 0 |
| FLW-DSN-009 | active |  |  | 0 | 0 |
| FLW-DSN-010 | active |  |  | 0 | 6 |
| FLW-DSN-011 | active |  |  | 0 | 3 |
| FLW-DSN-012 | active |  |  | 0 | 3 |
| FLW-DSN-013 | active |  |  | 0 | 2 |
| FLW-DSN-014 | active |  |  | 0 | 1 |
| FLW-FR-001 | 検証済み（verified） | governance | unit-test | 3 | 5 |
| FLW-FR-002 | 検証済み（verified） | tooling | manual-check | 1 | 1 |
| FLW-FR-003 | 実装中（implementing） | tooling | unit-test | 6 | 6 |
| FLW-FR-004 | 実装中（implementing） | tooling | unit-test | 2 | 2 |
| FLW-FR-005 | 承認済み（approved） | execution | unit-test | 0 | 0 |
| FLW-FR-006 | 承認済み（approved） | workflow | unit-test | 0 | 0 |
| FLW-FR-007 | 承認済み（approved） | tooling | unit-test | 0 | 0 |
| FLW-FR-008 | 承認済み（approved） | sync | unit-test | 0 | 0 |
| FLW-FR-009 | 承認済み（approved） | workflow | unit-test | 0 | 0 |
| FLW-FR-010 | 承認済み（approved） | workflow | unit-test | 0 | 0 |
| FLW-FR-011 | 承認済み（approved） | tooling | unit-test | 0 | 0 |
| FLW-FR-012 | 実装中（implementing） | governance | unit-test | 1 | 1 |
| FLW-NFR-001 | 実装中（implementing） | verification | benchmark | 8 | 8 |
| FLW-NFR-002 | 廃止（deprecated） | verification | benchmark | 0 | 0 |
| FLW-NFR-003 | 承認済み（approved） | execution | unit-test | 0 | 0 |
| FLW-NFR-004 | 実装中（implementing） | tooling | unit-test | 1 | 1 |
| FLW-NFR-005 | 承認済み（approved） | execution | unit-test | 0 | 0 |
| FLW-NFR-006 | 承認済み（approved） | execution | unit-test | 0 | 0 |
| FLW-NFR-007 | 承認済み（approved） | tooling | unit-test | 0 | 0 |
| FLW-NFR-008 | 実装中（implementing） | verification | benchmark | 4 | 4 |
| FLW-REV-002 | active |  |  | 0 | 0 |
| FLW-REV-003 | active |  |  | 0 | 0 |
| FLW-REV-004 | active |  |  | 0 | 0 |
| FLW-REV-005 | active |  |  | 0 | 0 |
| FLW-REV-006 | pending |  |  | 0 | 0 |

**判定: PASS ✅**
