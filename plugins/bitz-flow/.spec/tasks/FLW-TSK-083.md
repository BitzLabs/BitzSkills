---
implements: FLW-FR-006, FLW-CON-006, FLW-NFR-012
depends_on: FLW-TSK-082
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_cleanup.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/.spec/specs/m2-runtime/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-083.md, plugins/bitz-flow/.spec/STATE.md, evals/flow-core/m2-eval/qualification-2026-08-15-si-flw-057.json, evals/flow-core/m2-eval/active-local-confirmation.json, evals/flow-core/m2-eval/run-manifest-m2-remediation.json, tests/test_flow_m2_runtime.py, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### mutation境界の例外分類を是正しcreate/resumeのreconcile経路を定義する

- **作業内容**: `SI-FLW-057` を実装する。組み込み例外を遮蔽していた
  `RuntimeError(ValueError)` を `WorktreeRuntimeError` へ改名し、mutation 境界の except を
  plan 側と同じ閉集合へ揃える。`create` / `resume` が別 operation の step 列へ黙って
  照合されていた reconcile を是正し、未知 operation を既定へ倒さない。
- **検証**: 素の ValueError / KeyError による部分適用が PARTIAL として報告されること
  （旧コードで落ちる陽性対照つき）、create / resume の reconcile、実 receipt と
  cleanup 核の語彙一致、qualification 再実走、3platform confirmation、全pytest。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
