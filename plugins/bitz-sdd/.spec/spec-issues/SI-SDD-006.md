---
id: SI-SDD-006
raised_by: SI-CORE-028 の設計文書起票中に発見（2026-07-18）
target: sdd-core/scripts/spec_scaffold.py の next_number()（design 種別の採番衝突）
proposed_change_type: modify
status: accepted
---
- **目的**: `spec_scaffold.py` の `next_number()` は `^{prefix}-(\d+)\.md$` という厳格な正規表現で
  ディレクトリ内の既存ファイルをスキャンし最大番号+1を採番するが、設計ノート（DSN）は
  `DSN-001-delegation-registry.md` のように説明的サフィックスを付けて保存する慣行が既にある
  （既存の唯一の DSN 実例）。このサフィックス付きファイルは正規表現にマッチしないため走査から
  漏れ、次回 `design` 種別の起票で採番が「1」に戻り ID 重複を起こす。実際に SI-CORE-028 の設計
  文書起票時に `DSN-001.md` として重複生成され、`spec_inspect` の重複検出で発覚した（起票前に
  手動で回避済み）。
- **提案する修正**:
  1. `next_number()` の正規表現を `^{prefix}-(\d+)(-.*)?\.md$` 相当に緩め、サフィックス付き
     ファイル名からも番号を抽出できるようにする（他の種別 requirement/spec-issue/task は
     現状サフィックスを付けない運用のため影響は理論上小さいが、将来同様の慣行が生じても
     頑健になる）。
  2. 併せて、ファイル名でなく各ファイルの frontmatter `id:` フィールドを正として走査する方式へ
     切り替える案も検討する（ファイル名規約に依存しない、より堅牢な採番）。どちらを採るかは
     実装時に判断してよい（振る舞いを変えない範囲でのバグ修正のため軽量レーンで対応可能）。
  3. テスト先行: サフィックス付き既存ファイルがある状態で `design` 種別を scaffold し、
     重複しない番号が採番されることを確認する回帰テストを追加する。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py`、
  `tests/test_spec_scaffold.py`（該当テストファイルが無ければ新設）。
- **確認観点**: サフィックス付き DSN ファイルが存在する状態で新規 design を scaffold しても
  ID が重複しないこと。既存の requirement/spec-issue/task の採番動作に回帰がないこと
  （release_check / spec_inspect PASS、pytest green）。
- **影響推定・ロールバック**: `next_number()` 内部のみの修正で、生成される他成果物の書式は
  変わらない。単独 revert 可能。契約（`.spec` スキーマ・frontmatter 書式）自体は変更しないため
  軽量レーンで対応可（採番アルゴリズムのバグ修正であり、要件・受入基準の変更を伴わない）。
- **依存**: なし。
- **実施**: 2026-07-18 SDD-TSK-008（implements: CORE-FR-004）として軽量レーンで対応。
  `next_number()` の正規表現をサフィックス付きファイル名にも対応させ、回帰テスト
  `test_design_number_skips_suffixed_existing_file` を追加。pytest 159 green・release_check/
  spec_inspect（全6ワークスペース）PASS。bitz-sdd 1.11.1→1.11.2、sdd-core SKILL 1.13.1→1.13.2。
