---
implements: SDD-FR-110, SDD-FR-111
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-report/scripts/sdd_report.py, tests/test_sdd_report.py
status: done
---

### sdd_report.py の要件走査とタイトル抽出の修正（SI-SDD-001 / SI-SDD-002）

- **作業内容**:
  1. 要件走査を spec_inspect.py の load_requirements と同じ判定基準に揃える —
     `_` 始まりのファイルと `domains.md` を除外し、frontmatter に `id:` を
     持たないファイルは要件として数えない（SI-SDD-001）
  2. 要件タイトルを本文の最初の `### <ID> <タイトル>` 見出しから抽出する。
     frontmatter に `title:` があればそちらを優先する（SI-SDD-002）
  3. tests/test_sdd_report.py に回帰テストを追加する
     （domains.md 非集計・id 無しファイル非集計・見出しタイトル抽出・
     frontmatter title 優先・実要件のみでのヘルス判定）
- **由来**: SI-SDD-001 / SI-SDD-002（2026-07-12 人間裁定で accepted）。
  既存要件 SDD-FR-110/111 の範囲内のバグ修正のため新規要件なし（軽量レーン）。
- **実施記録**: 2026-07-12 実施完了。tests/test_sdd_report.py（5ケース）green、
  実環境（plugins/bitz-sdd ワークスペース）で 31件・Draft 0・GREEN・タイトル表示を実測確認。
  sdd-report v0.2.3 / bitz-sdd v1.4.6 に bump。
