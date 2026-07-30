---
implements: SDD-FR-155
depends_on: []
boundary: skills/sdd-core/scripts/spec_inspect.py, skills/sdd-core/scripts/spec_scaffold.py, tests/test_spec_inspect.py, tests/test_spec_scaffold.py
status: done
---

### GatePassage スキーマの検査と gate 種別の雛形生成を実装する

- **作業内容**: `spec_inspect.py` に `.spec/gates/` の走査を加え、frontmatter 必須7項目・
  `gate` 統制語彙・`scope` の実在（幽霊参照）・`confirmed_decision_refs` の参照先実在と
  ワークスペース外参照を検査する。ディレクトリが無いワークスペースでは無反応にする。
  複数値フィールドを読むため `parse_frontmatter_full`（ブロック / フロー両形式の
  シーケンス対応。`#` は前に空白がある場合のみコメント）を追加し、`checklist_ref` の
  アンカーを切り落とさないようにする。レポートに Gate 通過記録の節を追加する。
  `spec_scaffold.py` に `gate` 種別（`--gate` / `--arbiter` / `--scope` / `--decision-ref` /
  `--checklist-ref`）を追加し、必須フラグ不足は生成前に非ゼロで失敗させる。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
