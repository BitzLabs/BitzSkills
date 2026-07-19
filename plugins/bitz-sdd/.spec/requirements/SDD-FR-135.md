---
id: SDD-FR-135
version: 1.0
status: verified
domain: sync
priority: high
origin: SI-SDD-010
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-135 frontmatter境界を保持する本文双方向同期

- **説明**: `.spec/` と `docs/` は異なる frontmatter 契約を持つため、`sdd_sync.py` は
  ファイル全体をコピーせず、同期先固有の frontmatter を保持したまま本文だけを双方向同期する。
  日本語パスの対応は SDD-FR-126 / 128、mtime による新旧判定は SDD-FR-100 を維持する。
- **受入基準 (EARS)**:
  - WHEN `pull` が有効な frontmatter を持つ既存 docs 文書を更新するとき THEN システムは docs の frontmatter ブロックを変更せず保持する SHALL
  - WHEN `pull` が `.spec` 文書を docs 文書へ展開するとき THEN システムは `.spec` の frontmatter を除いた本文だけを docs 本文へ反映する SHALL
  - IF `pull` の `.spec` 同期元が有効な frontmatter を持たない THEN システムは docs 同期先を変更せずエラーを報告する SHALL
  - WHEN `pull` の docs 同期先が存在しないとき THEN システムは対応する同梱 docs テンプレートの frontmatter を付与する SHALL
  - WHEN `pull` の既存 docs 同期先が frontmatter を持たないとき THEN システムは対応する同梱 docs テンプレートの frontmatter を付与する SHALL
  - WHEN `pull` が同梱 docs テンプレートから frontmatter を生成するとき THEN システムは生成文書の `project_type` を `docs/MASTER.md` の有効な `project_type` と一致させる SHALL
  - IF `pull` が frontmatter を生成するときに `docs/MASTER.md` の `project_type` が無効である THEN システムは docs 同期先を変更せずエラーを報告する SHALL
  - IF `pull` の docs 同期先が閉じていない frontmatter を持つ THEN システムは当該ファイルを変更せずエラーを報告する SHALL
  - WHEN `push` が既存 `.spec` 文書を更新するとき THEN システムは `.spec` の frontmatter ブロックを変更せず保持する SHALL
  - WHEN `push` が docs 文書を `.spec` 文書へ逆反映するとき THEN システムは docs の frontmatter を除いた本文だけを `.spec` 本文へ反映する SHALL
  - IF `push` の docs 同期元が有効な frontmatter を持たない THEN システムは `.spec` 同期先を変更せずエラーを報告する SHALL
  - IF `push` の `.spec` 同期先が存在しない THEN システムは docs 固有 frontmatter で新規作成せずエラーを報告する SHALL
  - IF `push` の既存 `.spec` 同期先が frontmatter を持たない THEN システムは当該ファイルを変更せずエラーを報告する SHALL
  - IF `push` の既存 `.spec` 同期先が閉じていない frontmatter を持つ THEN システムは当該ファイルを変更せずエラーを報告する SHALL
  - WHEN pull が本文同期を完了したとき THEN システムは docs 同期先の mtime を `.spec` 同期元と同値に設定する SHALL
  - WHEN push が本文同期を完了したとき THEN システムは `.spec` 同期先の mtime を docs 同期元と同値に設定する SHALL
  - WHEN 日本語6章テンプレート上で `pull` の直後に `docs_inspect.py --strict` を実行したとき THEN システムは同期対象文書の frontmatter ERROR を0件にする SHALL
- **検証手段**: `tests/test_sdd_sync.py` の SDD-FR-135 unit-test（pull/push の双方の
  frontmatter 保持、本文同期、テンプレート生成、mtime 同値、異常系無変更、pull 後 strict PASS）。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（SI-SDD-010。SDD-FR-020 は SDD-FR-126 に置換済みのため、
    現行 SDD-FR-126 / 128 / 100 を維持する追加契約として補正）
