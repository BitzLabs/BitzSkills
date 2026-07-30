---
id: SDD-FR-155
version: 1.0
status: approved
domain: workflow
priority: high
origin: SI-SDD-028
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-155 GatePassage 成果物と .spec/gates/ スキーマを定義する

- **説明**: Gate（Discovery / Design / Promotion）の通過を、機械可読な独立成果物
  `GatePassage` として `.spec/gates/<NS>-GATE-NNN.md` に記録できるようにする。手順は
  `references/gates.md` に定義されているのに通過を表す成果物をどの機能も生成しておらず、
  「Gate が一度も実行されていない」ことを機械が言えなかった（SI-SDD-028、SDD-DSN-009 問題2）。
  裁定の理由と経緯は `.spec/reports/decision-*.md` が持つため、GatePassage は
  `confirmed_decision_refs` でそれを参照し二重管理しない。GatePassage は status 遷移を
  持たない不変の記録であり、要件・spec-issue・タスクのライフサイクル管理下には置かない。
  設計の正は SDD-DSN-010（裁定 D1・D2）。
- **受入基準 (EARS)**:
  - WHEN `spec inspect` が `.spec/gates/` 配下の成果物を検査する THEN frontmatter の `id`・`gate`・`date`・`arbiter`・`scope`・`confirmed_decision_refs`・`checklist_ref` の存在を検査し、欠落を不整合として報告すること SHALL
  - WHEN `gate` の値を検査する THEN `discovery`・`design`・`promotion` の統制語彙に限定し、語彙外の値を不整合として報告すること SHALL
  - WHEN `scope` に列挙された成果物 ID を検査する THEN 当該ワークスペースまたはクロスリファレンス解決先での実在を検査し、不在を幽霊参照として報告すること SHALL
  - WHEN `confirmed_decision_refs` の各要素を検査する THEN リポジトリ相対パス形式の参照先ファイルの実在を検査し、不在を不整合として報告すること SHALL
  - WHEN `spec scaffold <workspace> gate` を実行した THEN `.spec/gates/` 配下の次番号を決定的に採番し、`spec inspect` を PASS する雛形を生成すること SHALL
  - WHEN `.spec/gates/` が存在しないワークスペースを検査する THEN 当該検査をスキップし、不整合も警告も報告しないこと SHALL
  - WHEN GatePassage の status 遷移を要求した THEN `spec update` は GatePassage を遷移対象として扱わず拒否すること SHALL
- **検証手段**: `tests/test_spec_inspect.py`（frontmatter 必須項目・`gate` 統制語彙・`scope` の
  幽霊参照・`confirmed_decision_refs` の参照先実在・`.spec/gates/` 不在時の無反応）と
  `tests/test_spec_scaffold.py`（`gate` 種別の採番と雛形が PASS すること）で unit-test する。
  共有スクリプトの変更のため全 pytest と `release_check.py` を実行する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-028 の accepted 裁定と
    SDD-DSN-010 の Design Gate 裁定（D1・D2）から導出。
