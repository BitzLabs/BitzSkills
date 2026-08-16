---
implements: FLW-FR-006, FLW-FR-007, FLW-CON-005, FLW-NFR-011
depends_on: FLW-TSK-089
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/result.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py, plugins/bitz-flow/skills/flow-core/references/operation-catalog.md, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/design/FLW-DSN-014.md, plugins/bitz-flow/.spec/requirements/FLW-FR-006.md, plugins/bitz-flow/.spec/requirements/FLW-FR-007.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-082.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-083.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-084.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-085.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-086.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-087.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-088.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-089.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-090.md, plugins/bitz-flow/.spec/verification, plugins/bitz-flow/.spec/STATE.md, tests/test_flow_m2_runtime.py, evals/flow-core/m2-eval/active-local-confirmation.json, evals/flow-core/m2-eval/run-manifest-m2-remediation.json, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### auditの検出をquarantine語彙へ接続し出口条件と証跡の対応を確定する

- **作業内容**: `FLW-REV-017` の CONDITIONAL_PASS 通過条件のうち、独立レビューを要さない
  4件（`SYN-008` / `SYN-009` / `SYN-011` / `SYN-012`）を解消する。
  - `SYN-011`: 公開 `worktree.audit` の検出結果を設計語彙（`ORPHAN` / `quarantine_required` /
    §6 の解除区分）へ写し、`cause: "quarantined"` と `recovery_class` で quarantine へ接続する。
    receipt を読めない場合は `INDETERMINATE` とし分類を推測しない。
    `SKILL.md` の承認 capability 記述を catalog（B2 の規範）へ追随させる。
  - `SYN-009`: catalog へ audit の新しい振る舞いを記述し、`worktree.list` との責務差を書く。
    `FLW-TSK-086` の「実装不能」宣言を撤回に書き換える。
  - `SYN-008`: PR #289 / #290 / #291 に対応するタスクを遡って起票し、
    完了済みタスクの status を実体へ合わせる。
  - `SYN-012`: M2 出口条件8項目と現存証拠の対応表を `FLW-DSN-014` へ置き、
    出口4要件の status と検証証跡を前進させる。
- **範囲外**: `GP-005`（是正後の最終状態の独立レビュー）と business 観点の欠測は
  次の PR で扱う（裁定 2026-08-16）。
- **検証**: 陽性・陰性対照つきの quarantine 語彙テスト、`INDETERMINATE` 経路のテスト、
  既定 renderer での描画、qualification 再実走、3platform confirmation、全pytest、
  `release_check.py`、`spec inspect --check-only`。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
