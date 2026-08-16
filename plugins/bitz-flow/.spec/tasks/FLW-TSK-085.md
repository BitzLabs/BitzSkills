---
implements: FLW-NFR-011
depends_on: FLW-TSK-084
boundary: evals/flow-core/m2-eval/run_local_confirmation.py, evals/flow-core/m2-eval/qualification-2026-08-16-si-flw-058.json, evals/flow-core/m2-eval/active-local-confirmation.json, evals/flow-core/m2-eval/run-manifest-m2-remediation.json, tests/test_flow_m2_confirmation.py, plugins/bitz-flow/.spec/specs/m2-exit/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-085.md, plugins/bitz-flow/.spec/STATE.md, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### confirmation証跡をFLW-NFR-011の契約へ適合させる

- **作業内容**: `SI-FLW-058` の残り4項目を実装する。raw log を M1 の `raw_log_guard` で
  owner-only 境界・保持期限・削除担当つきに保存する（`SYN-004`）。manifest の operations を
  出荷表から導き、未公開 operation とワイルドカードを排する（`SYN-005`）。
  compatibility key の入力へ認可核と被測定 fixture を加え、`evidence_id` を分離する（`SYN-008`）。
  qualification fingerprint の 24 時間 TTL を照合し、confirmation evidence の 7 日期限を
  manifest へ宣言する（`SYN-009`）。hazard/residual の実測（`SYN-007`）は
  `FLW-TSK-084` で先行履行済み。
- **検証**: TTL の陽性対照（期限切れで起動しない）と陰性対照（期限内なら通る）、
  operations が出荷表と一致すること、認可核が指紋に含まれること、
  qualification 再実走、3platform confirmation、全pytest。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
