---
implements: FLW-FR-006, FLW-FR-007, FLW-CON-005
depends_on: FLW-TSK-087
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/.spec/specs/m2-runtime/test-spec.md, plugins/bitz-flow/.spec/spec-issues/SI-FLW-063.md, plugins/bitz-flow/.spec/spec-issues/SI-FLW-064.md, plugins/bitz-flow/.spec/STATE.md, evals/flow-core/m2-eval/active-local-confirmation.json, evals/flow-core/m2-eval/attempts-2026-08-16-si-flw-064.jsonl, evals/flow-core/m2-eval/qualification-2026-08-16-si-flw-064.json, evals/flow-core/m2-eval/run-manifest-m2-remediation.json, tests/test_flow_m2_runtime.py, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### receipt payloadへ変更対象を載せauditの外部変更検出を成立させる

- **作業内容**: `SI-FLW-064` を実装する（PR #290）。receipt の payload へ
  `action` / `path` / `branch` / `worktree_root` / `expected_head` を載せ、
  `managed_worktrees()` で DONE receipt から管理下 worktree を再構成する。
  `worktree.audit` が registry とこれを突き合わせ、operation 外の worktree を検出する。
- **先行宣言の撤回**: `FLW-TSK-086` が「検出は実装できない」と宣言していたが、
  payload に path が無いのは bitz-flow 自身の設計であり原理的制約ではなかった。
  同タスクの当該節は撤回済みである。
- **遡って起票した理由**: `FLW-TSK-087` と同じ（`FLW-REV-017:SYN-008` / `RVC-201`）。
- **検証**: 陽性対照（外部 `git worktree add` → BLOCKED）と陰性対照
  （operation が作った worktree は外部扱いにしない）、qualification 再実走、
  3platform confirmation、全pytest。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
