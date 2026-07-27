---
id: CORE-TSK-026
implements: CORE-FR-017
depends_on: []
boundary: docs/MASTER.md
status: done
---

### CORE-TSK-026 docs/MASTER.md の起票と excluded_paths 設定

- **作業内容**:
  `docs/MASTER.md` を更新/起票し、frontmatter の `excluded_paths` に SDD 管理対象外となる非構造化ドキュメント（`調査報告`, `archive` 等のフォルダおよび `improvement_master_plan.md` 等の単体ファイル）を明示的に指定する。
- **完了条件**:
  - `docs/MASTER.md` が存在し、`excluded_paths` に非管理パスが宣言されていること。
  - `docs_inspect.py` が `MASTER.md` から除外パスを正しく読み込めること。
