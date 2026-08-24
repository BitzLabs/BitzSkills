---
implements: FLW-NFR-014
depends_on: [FLW-TSK-121]
boundary: tests/test_flow_review_ledger.py,plugins/bitz-flow/.spec/reviews/FLW-REV-018.json,plugins/bitz-flow/.spec/reviews/FLW-REV-019.json,plugins/bitz-flow/.spec/reviews/FLW-REV-027.json,plugins/bitz-flow/.spec/reports/review-ledger-reconciliation.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### レビュー台帳の整合を機械検査し未解決P0/P1を照合する

`SI-FLW-091`（`FLW-REV-027` P2）。過去9レビューの未解決P0/P1が機械台帳上88件ある一方で、
後続レビューは`PASS`判定を出しており、台帳と判定が食い違って見える。

- **実測した状態**:
  - `FLW-REV-027`の`carried_over`（88件）は、先行レビューの未解決（`open`／`tracked`）
    P0/P1と**完全に一致**していた。欠落も余剰も0件であり、生成そのものは正しい。
  - 一方、その一致を**検査する仕組みが無い**。台帳がずれても誰も気づかない。
  - `tracked`の`tracked_by`が実在するspec-issueまたはgate preconditionを指すかも未検査。
  - `resolved`へ遷移した findingが証跡を持つかも未検査。
- **作業内容**:
  - `tests/test_flow_review_ledger.py`を追加し、次を機械検査する。
    最新レビューの`carried_over`が未解決P0/P1と**厳密一致**すること（欠落を許さない）。
    `status`が既知の語彙であること。`tracked`の`tracked_by`が実在するspec-issueまたは
    同一レビューの`gate_preconditions`を指すこと。`resolved`が証跡（`resolved_by`）を持つこと。
  - **機械的に証明できる findingだけ**を`resolved`へ照合する。証拠は実在する
    schema・test・taskを名指しする。証明できないものは`tracked`のまま残し、
    憶測でresolvedにしない。
  - 照合の経緯と、照合できなかった理由を
    `.spec/reports/review-ledger-reconciliation.md`へ記録する。
- **完了条件**:
  - 未解決P0/P1が最新レビューの`carried_over`から欠落しないこと（機械検査）。
  - `resolved`化した findingがすべて実在する修正・検証証跡を名指ししていること。
  - 履歴内容を削除せず、`status`と参照だけを修正していること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: runtime挙動を変えない。88件の一括resolved化は行わない
  （証跡を伴わないresolved化は`FLW-REV-027`が指摘した過大主張そのものであるため）。
