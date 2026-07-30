---
id: SDD-FR-156
version: 1.0
status: approved
domain: workflow
priority: high
origin: SI-SDD-028
verification_method: unit-test
derived_from: SDD-FR-145
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-156 未検分の代行遷移を decision_ref 単位で判定し滞留を可視化する

- **説明**: 代行可視化経路（SDD-FR-145）は「裁定の真正性は機械検証されない。Promotion Gate で
  人間が decision-ref を確認する」ことを唯一の担保としており、その担保が行使されているかを
  機械が言えるようにする。**検分の単位は対象要件の promoted 到達ではなく `decision_ref`**
  とする — 代行遷移は spec-issue の `open → accepted` にも起きており、spec-issue は
  `promoted` 状態を持たないため要件基準では永久に滞留扱いになる（SDD-DSN-010 裁定 D2 が
  SI-SDD-028 提案1 の定義を上書きした）。可視化は `spec status` の JSON へ加算のみで行い、
  既存キーの意味と型は変えない。閾値は宣言せず件数の可視化を先行する（裁定 D4）——
  宣言だけして機械集計を伴わなかった過去の失敗（SI-SDD-029）を繰り返さないため。
- **受入基準 (EARS)**:
  - WHEN `spec status` が STATE の構造化 event を集計する THEN `provenance.kind` が `agent-proxy-unverified` の event のうち、その `provenance.decision_ref` がいずれの GatePassage の `confirmed_decision_refs` にも現れないものを未検分と判定すること SHALL
  - WHEN 対象が spec-issue である代行遷移を判定する THEN 対象成果物が `promoted` に到達したかを判定条件に用いず、`decision_ref` の検分有無のみで判定すること SHALL
  - WHEN 未検分の代行遷移が1件以上ある THEN `--json` 出力へ `unreviewed_proxy_decisions`（`count`・`oldest_age_days`・`decision_refs`）を加算のみで追加し、既存キーの名称・意味・型を変更しないこと SHALL
  - WHEN 未検分の代行遷移が1件以上ある THEN 人間向け出力の次アクション候補へ件数と最古の滞留日数を提示すること SHALL
  - WHEN 未検分の代行遷移が0件である THEN 次アクション候補に当該項目を出力しないこと SHALL
  - WHEN `.spec/gates/` が存在しないワークスペースを集計する THEN すべての代行遷移を未検分として扱い、集計の失敗として終了しないこと SHALL
  - WHEN `adoption-metrics.md` が本項目を定義する THEN 「未検分の代行遷移件数」と「最古の滞留日数」を機械集計の実装を伴う形で定義し、閾値は宣言しないこと SHALL
- **検証手段**: `tests/test_spec_status.py`（decision_ref 単位の判定、spec-issue 遷移の扱い、
  JSON への加算キー、滞留ゼロでの無出力、`.spec/gates/` 不在時の劣化動作）で unit-test する。
  `adoption-metrics.md` の計測項目定義が機械集計と対応することを同テストで検査する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-028 提案1・2 と
    SDD-DSN-010 の Design Gate 裁定（D2・D4）から導出。
