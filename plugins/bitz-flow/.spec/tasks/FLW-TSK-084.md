---
implements: FLW-NFR-011, FLW-NFR-012
depends_on: FLW-TSK-082
boundary: evals/flow-core/m1-eval/run_qualification.py, evals/flow-core/m2-eval/run_local_confirmation.py, evals/flow-core/m2-eval/qualification-2026-08-16-si-flw-062.json, evals/flow-core/m2-eval/active-local-confirmation.json, tests/test_flow_m1_qualification_runner.py, plugins/bitz-flow/.spec/spec-issues/SI-FLW-062.md, plugins/bitz-flow/.spec/reports/decision-2026-08-16-si-flw-062.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-084.md, plugins/bitz-flow/.spec/STATE.md, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### eval harnessから被験リポジトリの書き込み権限を取り上げhazardを実測する

- **作業内容**: `SI-FLW-062` を実装する。qualification は被験リポジトリを cwd にせず
  使い捨て fixture で実行し、antigravity から `--sandbox=false` /
  `--dangerously-skip-permissions` を外す。被験リポジトリの状態（HEAD・ref・作業ツリー・
  worktree 一覧）を trial 前後で実測し、変化を hazard / residual として記録する。
  timeout 時も副作用を確認してから BLOCKED を確定する。confirmation は cwd を隔離できないため
  前後比較で hazard を実測する（従来の `0 if valid else 1` の固定写像をやめる）。
- **検証**: hazard 検出の陽性対照（被験リポジトリへコミットする偽 CLI で hazard が立つ）と
  陰性対照（触らなければ立たない）、書き込みフラグ不在の機械検査、qualification 再実走、
  3platform confirmation、全pytest。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
