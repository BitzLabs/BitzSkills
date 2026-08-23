---
implements: FLW-NFR-014
depends_on: [FLW-TSK-110,FLW-TSK-113]
boundary: plugins/bitz-flow/skills/flow-core/references/operation-catalog.md,plugins/bitz-flow/skills/flow-core/references/m2-operability-coverage.json,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_operability.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/recovery.py,plugins/bitz-flow/docs/runbooks/m2-worktree-quarantine.md,tests/test_flow_m2_operability.py,tests/test_flow_m1_contract_rows.py,tests/test_flow_m2_confirmation.py,evals/flow-core/m2-eval/local_confirmation_subject.py,evals/flow-core/m2-eval/run_local_confirmation.py,evals/flow-core/m2-eval/qualification-2026-08-23-flw-tsk-114.json,evals/flow-core/m2-eval/active-local-confirmation.json,evals/flow-core/m2-eval/attempts.jsonl,evals/flow-core/m2-eval/raw/claude.log,evals/flow-core/m2-eval/raw/codex.log,evals/flow-core/m2-eval/raw/antigravity.log,plugins/bitz-flow/skills/flow-core/SKILL.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json,.claude-plugin/marketplace.json
status: done
---

### doctor・audit・verify-receipt・reconcileを統合する

- **作業内容**: 既存の`worktree <action>` grammarへdoctor、audit、verify-receipt、reconcileを接続する。
  - read-only commandは実行前後のpersistent state digest不変を検査する。
  - reconcileだけが明示確認後に下位API経由でclosure eventを追記できる。
  - closed resultへcause、side-effect state、自動復旧可否、operator action、receipt参照、journal使用量を含める。
  - 非対応承認方式を公開`UNSUPPORTED` + `unsupported-approval-mode`として表示し、内部reasonを漏らさない。
  - RBAC、通知adapter、RTO/SLO、key lifecycle、archive/prune/restoreを実装しない。
- **完了条件**: 全commandが実在し、read-only副作用0件、停止時operator action欠落0件、
  reconcileのGit副作用0件、journal/receipt自動削除0件、FLW-DSN-017 §7.1の全適用行と§8.1の全edgeを
  E2E coverage manifestで確認する。
- **見積り**: FLW-TSK-110と実装PR 6へまとめ、2 sessionを上限とする。
- **実行判定**: 運用統合の最終task。下位の安全判定をCLI独自logicで上書きしない。
