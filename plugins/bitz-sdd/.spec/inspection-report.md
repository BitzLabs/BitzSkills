# inspection-report.md (2026-07-30)

成果物数: 99 / 問題: 0 / 幽霊参照: 2 / 実装待ち: 0 / 孤児要件: 0 / 検証証跡: 2

## 問題一覧
- なし ✅

## 幽霊参照（存在しないIDへの参照）
- DSN-007 ← .spec/tasks/SDD-TSK-051.md
- DSN-009 ← .spec/tasks/SDD-TSK-051.md

## 監査 WARN（代行遷移の裁定参照など — FAIL にしない）
- なし ✅

## 実装待ち要件（approved だが implements するタスクがない — WARN）
- なし ✅

## 孤児要件（implementing以降なのに implements するタスクがない）
- なし ✅

## テスト/実装からの参照がない要件（approved以降）
- SDD-FR-010
- SDD-FR-041
- SDD-FR-100
- SDD-FR-125
- SDD-FR-126
- SDD-FR-127
- SDD-FR-128
- SDD-FR-129
- SDD-FR-131
- SDD-FR-135

## 参照がない manual-check 要件（テスト参照は原理的に生じない — 検証記録で担保）
- SDD-CON-022
- SDD-CON-032
- SDD-CON-042
- SDD-CON-043
- SDD-CON-050
- SDD-CON-052
- SDD-FR-011
- SDD-FR-021
- SDD-FR-031
- SDD-FR-033
- SDD-FR-051
- SDD-FR-053
- SDD-FR-060
- SDD-FR-061
- SDD-FR-070
- SDD-FR-071
- SDD-FR-080
- SDD-FR-081
- SDD-FR-082
- SDD-FR-090
- SDD-FR-091
- SDD-FR-110
- SDD-FR-111
- SDD-FR-112
- SDD-FR-120
- SDD-FR-121
- SDD-FR-122
- SDD-FR-123
- SDD-FR-130

## 他ワークスペースのテスト/実装から参照されている要件
- SDD-FR-124 ← BitzSkills/tests/test_spec_inspect.py, BitzSkills/tests/test_spec_scaffold.py
- SDD-FR-133 ← BitzSkills/tests/test_spec_inspect.py
- SDD-FR-134 ← BitzSkills/tests/test_spec_inspect.py
- SDD-FR-140 ← BitzSkills/scripts/release_check.py, BitzSkills/tests/test_release_check.py
- SDD-FR-149 ← BitzSkills/tests/test_sdd_sync.py

## 検証証跡（.spec/verification/ — 実出力に基づく機械可読証跡）
※ 実行時間は observed（非正規）であり一致判定に使わない。判定は exit_code と件数が正
- .spec/verification/pytest--5526358.json — commit 5526358 / exit_code 0 / 対象 SDD-FR-162
- .spec/verification/pytest--d5a446c.json — commit d5a446c / exit_code 0 / 対象 SDD-FR-151, SDD-FR-152, SDD-FR-153, SDD-FR-154

## 検証証跡の WARN（古い commit・証跡なしの verified 要件 — FAIL にしない）
- [verify] .spec/verification/pytest--5526358.json: 記録時の commit(5526358) 以降にソースが変更されています（再記録が必要な可能性）
- [verify] .spec/verification/pytest--d5a446c.json: 記録時の commit(d5a446c) 以降にソースが変更されています（再記録が必要な可能性）
- [verify] SDD-FR-001: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-010: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-041: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-100: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-124: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-125: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-126: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-127: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-128: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-129: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-131: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-132: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-133: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-134: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-135: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-136: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-137: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-138: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-139: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-140: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-141: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-142: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-143: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-144: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-145: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-146: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-147: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-148: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-149: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-150: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-155: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-156: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-157: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-158: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-159: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-160: verified/promoted だが検証証跡がありません
- [verify] SDD-FR-161: verified/promoted だが検証証跡がありません

## docs 乖離（派生元 docs が派生後に変更された要件 — stale 候補）
※ 乖離は候補提示のみ。stale 付与は references/lifecycle.md の再伝播プロトコル（判定パス→人間確認）を経ること
- なし ✅

## Traceability Matrix
| ID | status | domain | v-method | tasks | 参照元数 |
|----|--------|--------|----------|-------|----------|
| SDD-CON-022 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-CON-032 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-CON-042 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-CON-043 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-CON-050 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-CON-052 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-DSC-001 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSC-002 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSC-003 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSC-004 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSC-005 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSC-006 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSN-000 | active |  |  | 0 | 0 |
| SDD-DSN-001 | active |  |  | 0 | 0 |
| SDD-DSN-002 | active |  |  | 0 | 1 |
| SDD-DSN-003 | active |  |  | 0 | 0 |
| SDD-DSN-004 | active |  |  | 0 | 3 |
| SDD-DSN-005 | active |  |  | 0 | 1 |
| SDD-DSN-006 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSN-007 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSN-008 | 起草中（draft） |  |  | 0 | 0 |
| SDD-DSN-009 | 起草中（draft） |  |  | 0 | 1 |
| SDD-DSN-010 | active |  |  | 0 | 1 |
| SDD-DSN-011 | active |  |  | 0 | 0 |
| SDD-FR-001 | 検証済み（verified） | verification | example-test | 1 | 3 |
| SDD-FR-010 | 検証済み（verified） | verification | example-test | 1 | 1 |
| SDD-FR-011 | 検証済み（verified） | workflow | manual-check | 1 | 1 |
| SDD-FR-020 | 廃止（deprecated） | upstream | example-test | 1 | 1 |
| SDD-FR-021 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-FR-030 | 廃止（deprecated） | upstream | example-test | 1 | 1 |
| SDD-FR-031 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-FR-033 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-FR-040 | 廃止（deprecated） | upstream | example-test | 1 | 1 |
| SDD-FR-041 | 検証済み（verified） | upstream | example-test | 1 | 1 |
| SDD-FR-051 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-FR-053 | 検証済み（verified） | upstream | manual-check | 1 | 1 |
| SDD-FR-060 | 検証済み（verified） | verification | manual-check | 1 | 1 |
| SDD-FR-061 | 検証済み（verified） | verification | manual-check | 1 | 1 |
| SDD-FR-070 | 検証済み（verified） | execution | manual-check | 1 | 1 |
| SDD-FR-071 | 検証済み（verified） | execution | manual-check | 1 | 1 |
| SDD-FR-080 | 検証済み（verified） | execution | manual-check | 1 | 1 |
| SDD-FR-081 | 検証済み（verified） | execution | manual-check | 1 | 1 |
| SDD-FR-082 | 検証済み（verified） | execution | manual-check | 1 | 1 |
| SDD-FR-090 | 検証済み（verified） | verification | manual-check | 1 | 1 |
| SDD-FR-091 | 検証済み（verified） | verification | manual-check | 1 | 1 |
| SDD-FR-100 | 検証済み（verified） | sync | example-test | 1 | 2 |
| SDD-FR-101 | 廃止（deprecated） | sync | example-test | 1 | 1 |
| SDD-FR-110 | 検証済み（verified） | reporting | manual-check | 2 | 2 |
| SDD-FR-111 | 検証済み（verified） | reporting | manual-check | 2 | 2 |
| SDD-FR-112 | 検証済み（verified） | execution | manual-check | 1 | 2 |
| SDD-FR-120 | 検証済み（verified） | workflow | manual-check | 2 | 4 |
| SDD-FR-121 | 検証済み（verified） | workflow | manual-check | 2 | 4 |
| SDD-FR-122 | 検証済み（verified） | execution | manual-check | 1 | 2 |
| SDD-FR-123 | 検証済み（verified） | verification | manual-check | 1 | 2 |
| SDD-FR-124 | 検証済み（verified） | verification | example-test | 1 | 2 |
| SDD-FR-125 | 検証済み（verified） | sync | unit-test | 2 | 3 |
| SDD-FR-126 | 検証済み（verified） | sync | unit-test | 2 | 4 |
| SDD-FR-127 | 検証済み（verified） | sync | unit-test | 2 | 4 |
| SDD-FR-128 | 検証済み（verified） | sync | unit-test | 2 | 3 |
| SDD-FR-129 | 検証済み（verified） | sync | unit-test | 2 | 3 |
| SDD-FR-130 | 検証済み（verified） | workflow | manual-check | 1 | 1 |
| SDD-FR-131 | 検証済み（verified） | workflow | unit-test | 1 | 1 |
| SDD-FR-132 | 検証済み（verified） | verification | example-test | 1 | 3 |
| SDD-FR-133 | 検証済み（verified） | verification | unit-test | 1 | 2 |
| SDD-FR-134 | 検証済み（verified） | verification | unit-test | 1 | 2 |
| SDD-FR-135 | 検証済み（verified） | sync | unit-test | 1 | 2 |
| SDD-FR-136 | 検証済み（verified） | workflow | unit-test | 1 | 4 |
| SDD-FR-137 | 検証済み（verified） | workflow | unit-test | 1 | 3 |
| SDD-FR-138 | 検証済み（verified） | workflow | unit-test | 1 | 3 |
| SDD-FR-139 | 検証済み（verified） | workflow | unit-test | 1 | 2 |
| SDD-FR-140 | 検証済み（verified） | workflow | unit-test | 1 | 2 |
| SDD-FR-141 | 検証済み（verified） | reporting | example-test | 3 | 4 |
| SDD-FR-142 | 検証済み（verified） | reporting | example-test | 3 | 4 |
| SDD-FR-143 | 検証済み（verified） | workflow | unit-test | 3 | 9 |
| SDD-FR-144 | 検証済み（verified） | workflow | unit-test | 2 | 5 |
| SDD-FR-145 | 検証済み（verified） | workflow | unit-test | 3 | 8 |
| SDD-FR-146 | 検証済み（verified） | verification | unit-test | 1 | 3 |
| SDD-FR-147 | 検証済み（verified） | verification | unit-test | 1 | 3 |
| SDD-FR-148 | 検証済み（verified） | verification | unit-test | 1 | 3 |
| SDD-FR-149 | 検証済み（verified） | sync | unit-test | 1 | 2 |
| SDD-FR-150 | 検証済み（verified） | sync | unit-test | 1 | 3 |
| SDD-FR-151 | 検証済み（verified） | verification | unit-test | 1 | 5 |
| SDD-FR-152 | 検証済み（verified） | verification | unit-test | 1 | 3 |
| SDD-FR-153 | 検証済み（verified） | verification | unit-test | 1 | 3 |
| SDD-FR-154 | 検証済み（verified） | reporting | unit-test | 1 | 3 |
| SDD-FR-155 | 検証済み（verified） | workflow | unit-test | 1 | 3 |
| SDD-FR-156 | 検証済み（verified） | workflow | unit-test | 1 | 2 |
| SDD-FR-157 | 検証済み（verified） | workflow | unit-test | 1 | 2 |
| SDD-FR-158 | 検証済み（verified） | verification | unit-test | 1 | 2 |
| SDD-FR-159 | 検証済み（verified） | verification | unit-test | 1 | 2 |
| SDD-FR-160 | 検証済み（verified） | verification | unit-test | 1 | 3 |
| SDD-FR-161 | 検証済み（verified） | verification | unit-test | 1 | 2 |
| SDD-FR-162 | 検証済み（verified） | verification | unit-test | 1 | 3 |
| SDD-FR-163 | 実装中（implementing） | reporting | unit-test | 1 | 2 |
| SDD-REV-002 | active |  |  | 0 | 1 |
| SDD-REV-003 | active |  |  | 0 | 0 |
| SDD-REV-004 | active |  |  | 0 | 0 |
| SDD-REV-005 | active |  |  | 0 | 1 |
| SDD-REV-006 | active |  |  | 0 | 0 |

**判定: FAIL ❌（上記を解消するまで verified に進めない）**
