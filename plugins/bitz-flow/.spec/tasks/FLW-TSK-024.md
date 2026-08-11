---
implements: FLW-NFR-010
depends_on: []
boundary: evals/flow-core/m0-eval/run_codex.py,evals/flow-core/m0-eval/run_claude.py,evals/flow-core/m0-eval/run_antigravity.py,plugins/bitz-flow/.spec/design/FLW-DSN-014.md,tests/test_m0_eval_scoring.py,plugins/bitz-flow/.spec/specs/agent-unavailable/test-spec.md
status: done
---

### platform固有の測定不能署名とraw log永続化を固定する

- **作業内容**:
  - Claudeの`rate_limit_event.status == rejected`と`is_error`補助条件を専用回帰で固定する。
  - Codex・Antigravityの拒否署名と、実行痕跡がある場合のfalse positive防止を固定する。
  - raw stdout/stderrを単一の決定的JSONへ既定保存し、trialから解決可能な相対pathを記録する。
  - proxy台帳のplatform固有oracleと証跡path契約を実装に合わせて明記する。
- **完了条件**: 3 runnerの拒否署名、無実行痕跡、raw log既定保存・digest解決がunit testでgreenになり、
  全テスト・spec inspect・release checkがPASSすること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
