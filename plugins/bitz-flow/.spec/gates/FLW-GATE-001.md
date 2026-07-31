---
id: FLW-GATE-001
gate: design
date: 2026-07-29
arbiter: hide
scope: [FLW-DSN-000, FLW-DSN-002, FLW-DSN-003, FLW-DSN-004, FLW-DSN-005, FLW-DSN-006, FLW-DSN-007, FLW-DSN-008, FLW-DSN-009, FLW-DSN-010, FLW-DSN-011, FLW-DSN-012, FLW-DSN-013, FLW-DSN-014]
confirmed_decision_refs:
  - .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
checklist_ref: skills/sdd-core/references/gates.md#2-design-gateproposed--active
---

# FLW-GATE-001 bitz-flow v2 Design Gate 通過記録

- **裁定者**: hide
- **対象**: 上記 `scope` の 14 件（active 化した設計成果物）に加え、同じ裁定で accepted とした
  `SI-FLW-002` / `SI-FLW-003` / `SI-FLW-004` / `SI-FLW-005` の4件。spec-issue は `scope` に
  列挙していない — `spec_inspect.py` の `check_gate_passages` が `scope` を要件・設計レジストリ
  （`global_reqs`）だけで解決するため、spec-issue ID を書くと幽霊参照として FAIL する。
  代行遷移の検分判定は `decision_ref` 単位（`spec_status.py` の `unreviewed_proxy_decisions`）
  であり、下記 `confirmed_decision_refs` によって4件とも検分済みになる。
- **確認した裁定記録**: 上記 `confirmed_decision_refs`
- **チェックリスト**: `skills/sdd-core/references/gates.md#2-design-gateproposed--active`
- **備考**: `date` は Gate を実行した日（2026-07-29）である。本記録ファイル自体は
  2026-07-31 に遡及して起票した。GatePassage 機構（SDD-FR-155〜157）が bitz-sdd へ
  導入されたのが当該 Design Gate より後であり、`scope` の spec-issue 4件は
  `open → accepted` の代行遷移で promoted 状態を持たないため、GatePassage が
  `confirmed_decision_refs` を持たない限り `spec status` の未検分として滞留し続ける。
  遡及起票の裁定は `.spec/reports/decision-2026-07-31-bitz-flow-roadmap-open-issues.md`（論点6）。
  裁定日・裁定者・対象・裁定記録はいずれも 2026-07-29 の実在事実であり、本記録はそれを
  機械可読へ写したものである（新たな裁定を行っていない）。
