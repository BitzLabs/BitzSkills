---
implements: FLW-FR-006, FLW-CON-005, FLW-NFR-011
depends_on: FLW-TSK-081
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/references/operation-catalog.md, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/spec-issues/SI-FLW-061.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-082.md, plugins/bitz-flow/.spec/STATE.md, evals/flow-core/m2-eval/record_run.py, evals/flow-core/m2-eval/run-manifest-m2-remediation.json, evals/flow-core/m2-eval/qualification-2026-08-15-si-flw-061.json, evals/flow-core/m2-eval/active-local-confirmation.json, tests/test_flow_m2_runtime.py, tests/test_flow_m2_run_manifest.py, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### 承認capabilityをplan-digest既定へ縮退しregistry境界を是正する

- **作業内容**: `SI-FLW-061`（B2）を実装する。承認モードを配備で決め、既定は
  `--confirm <operation_id>` と `operation_id` 由来の単回 nonce だけで承認する。
  trusted key registry がある配備でのみ署名を要求し、`apply()` 自身が registry を読む。
  承認モードを result へ出す。あわせて `SI-FLW-058` の run manifest 記録機構を先行履行する
  （2026-08-15 予算裁定の着手条件）。
- **検証**: 2モードの承認 fixture、nonce 導出と再利用拒否、qualification 再実走、
  3platform confirmation、全pytest、spec inspect、release check。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
