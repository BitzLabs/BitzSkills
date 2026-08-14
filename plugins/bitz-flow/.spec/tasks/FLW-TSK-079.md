---
implements: FLW-FR-005, FLW-CON-006, FLW-NFR-011
depends_on: [FLW-TSK-078]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/remote_delete.py, evals/flow-core/m2-eval/local_confirmation_subject.py, evals/flow-core/m2-eval/run_local_confirmation.py, evals/flow-core/m2-eval/qualification-2026-08-14-m2-exit.json, evals/flow-core/m2-eval/active-local-confirmation.json, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/specs/m2-exit/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-079.md, tests/test_flow_m2_remote_delete.py, tests/test_flow_m2_confirmation.py, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### M2-6 remote-delete安全核とlocal-write confirmationを完了する

- **作業内容**: expected-OID CAS、Activity API三経路、remote-write M3縮退、qualification
  fingerprint再照合、3platform local-write confirmation harnessを実装する。
- **検証**: `M2-FLT-037`〜`044`、`048`、`049`、`054`、3platform actual confirmation、
  全テスト、spec inspection、release check。
