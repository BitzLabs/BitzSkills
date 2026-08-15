---
implements: FLW-FR-006, FLW-FR-007, FLW-CON-005
depends_on: FLW-TSK-085
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/references/operation-catalog.md, plugins/bitz-flow/.spec/specs/m2-runtime/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-086.md, plugins/bitz-flow/.spec/STATE.md, evals/flow-core/m2-eval/qualification-2026-08-16-si-flw-059.json, evals/flow-core/m2-eval/active-local-confirmation.json, evals/flow-core/m2-eval/run-manifest-m2-remediation.json, tests/test_flow_m2_runtime.py, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### 公開dispatcher経由のworktree E2Eとauditの契約層接続

- **作業内容**: `SI-FLW-059` を実装する。`cli.main()` へ fixture 専用のハンドラ表注入口を設け
  （裁定 2026-08-16 案A）、`create` / `resume` と主要 fault 経路を公開経路の E2E で検証する。
  `worktree.audit` を契約層へ載せる（失敗を result にする・`--limit` を尊重する）。
- **未実装として宣言する範囲**: operation 外の変更検出は行わない。git の registry は
  `git worktree add` で必ず登録されるため registry 照合では区別できず、bitz-flow 自身の
  receipt と突き合わせる必要があるが payload に path が無い（`FLW-REV-016:SYN-013`）。
  動かない検出器を出荷せず、`data.external_change_detection` で不可を宣言する。
- **検証**: 公開経路の create → resume、confirm 不一致・承認使い回し・confirm 欠如の停止、
  既定表では worktree へ到達できないこと、audit の `--limit` と result 化、
  qualification 再実走、3platform confirmation、全pytest。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
