---
implements: FLW-FR-006, FLW-NFR-011
depends_on: FLW-TSK-088
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, tests/test_flow_m2_runtime.py, plugins/bitz-flow/.spec/spec-issues/SI-FLW-065.md, plugins/bitz-flow/.spec/spec-issues/SI-FLW-066.md, plugins/bitz-flow/.spec/reviews/FLW-REV-017.md, plugins/bitz-flow/.spec/reviews/FLW-REV-017.json, plugins/bitz-flow/.spec/reviews/individual/flw-rev-017-consistency.json, plugins/bitz-flow/.spec/reports/decision-2026-08-16-flw-rev-017-completion-gate.md, plugins/bitz-flow/.spec/STATE.md, evals/flow-core/m2-eval/active-local-confirmation.json, evals/flow-core/m2-eval/attempts-2026-08-16-si-flw-065.jsonl, evals/flow-core/m2-eval/qualification-2026-08-16-si-flw-065.json, evals/flow-core/m2-eval/run-manifest-m2-remediation.json, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### 既定出力形式のKeyErrorを是正しM2 Exit再々レビューを確定する

- **作業内容**: `SI-FLW-065` を実装する（PR #291）。`worktree.audit` の `next_actions` を
  `R.next_action()` の契約形（`domain` / `action` / `args`）へ直し、
  **公開経路 E2E が既定 renderer を必ず通る**専用テストを置く。
  あわせて `FLW-REV-017` を4観点で確定し、Completion Gate の保留を裁定記録へ残す。
- **見落としの構造**: 公開経路 E2E のヘルパが `--format json` を固定しており、
  dispatcher テストが既定 renderer を一度も通っていなかった。
  既定形式は利用者が実際に見る出力である。
- **遡って起票した理由**: `FLW-TSK-087` と同じ（`FLW-REV-017:SYN-008` / `RVC-201`）。
- **検証**: 既定形式での全公開 operation 描画、qualification 再実走、
  3platform confirmation（フォアグラウンドで再試行 0 回）、全pytest、`release_check.py`。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
