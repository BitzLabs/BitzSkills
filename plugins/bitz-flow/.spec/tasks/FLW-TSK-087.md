---
implements: FLW-NFR-011, FLW-NFR-012
depends_on: FLW-TSK-086
boundary: scripts/agy_guard.py, tests/test_agy_guard.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py, evals/flow-core/m2-eval/run_local_confirmation.py, evals/flow-core/m2-eval/active-local-confirmation.json, evals/flow-core/m2-eval/attempts-2026-08-16-si-flw-063.jsonl, evals/flow-core/m2-eval/qualification-2026-08-16-si-flw-063.json, evals/flow-core/m2-eval/run-manifest-m2-remediation.json, plugins/bitz-flow/.spec/spec-issues/SI-FLW-063.md, plugins/bitz-flow/.spec/STATE.md, tests/test_flow_m2_confirmation.py, tests/test_flow_m2_runtime.py, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### ガード迂回と承認由来の偽装を是正し証跡契約を補う

- **作業内容**: `SI-FLW-063` を実装する（PR #289）。`agy_guard.py` の allowlist を
  **実測した payload** に基づいて組み直し（`CommandLine` 一致・`BypassSandbox` 非真・
  `Cwd` にメタ文字なし・未知 field なし）、DENY 走査を allow より前に置く。
  `approval_source` が無条件に `signed-capability` を名乗る偽装を是正する。
  復旧経路まで例外分類の是正を届かせ、attempt 台帳を導入する。
- **遡って起票した理由**: 本タスクは PR がマージされた後に起票した。
  `SI-FLW-063` / `SI-FLW-064` に対応する task が存在せず、boundary 宣言と実際の
  変更集合が乖離していた（`FLW-REV-017:SYN-008` / `RVC-201`）。
  以後は「task 無しで実装 PR を出さない」を予算消費の記録条件とする。
- **検証**: 相乗り拒否と正規経路 PASS の両立、qualification 再実走、
  3platform confirmation、全pytest、`release_check.py`。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
