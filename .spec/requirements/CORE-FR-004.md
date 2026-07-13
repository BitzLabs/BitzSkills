---
id: CORE-FR-004
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-012（プロジェクト改修計画 2026-07-12 ユーザー要望3。定型処理のスクリプト化）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-004 spec_scaffold.py による採番付き雛形生成

- **説明**: 要件 / spec-issue / タスクの新規起票時に、プレフィックスごとの次番号を決定的に採番し、
  frontmatter 付きの雛形を生成する読み取り主体のスクリプト `spec_scaffold.py` を提供する。
  エージェントが毎回手書きしていた採番・雛形生成を機械化し、書式ブレと採番衝突を構造的に防ぐ。
- **受入基準 (EARS)**:
  - WHEN 種別（requirement / spec-issue / task）とプレフィックスを指定して起票する THEN 当該プレフィックスの既存 ID を走査し「最大番号 + 1」を採番すること SHALL
  - WHEN 同一プレフィックスの既存 ID が存在しない状態で起票する THEN 001 を採番すること SHALL
  - WHEN 雛形を生成する THEN 生成物の frontmatter は spec_inspect.py の検証を PASS する書式互換（既存手書きファイルと同一のキー構成）であること SHALL
  - WHERE 指定パスに同名ファイルが既に存在する THEN 上書きせず非ゼロで失敗すること SHALL
  - THEN spec_scaffold.py の副作用は指定ワークスペースの `.spec/` 配下への新規ファイル生成のみに限定されること SHALL
- **検証手段**: tests/test_spec_scaffold.py（テスト先行）。採番の一意性・連番、001 起番、
  生成物の spec_inspect PASS、既存ファイル非上書き、書式互換を example-test で検証する。
- **Revision History**:
  - 1.0 (2026-07-13) 初版（SI-CORE-012 の要件化ドラフト。テスト先行）
  - 1.0 (2026-07-13) 人間裁定により approved 化（チャット指示）
