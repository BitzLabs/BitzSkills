---
id: QLT-FR-002
version: 1.0
status: verified
domain: quality-init
priority: high
origin: プラグイン初期化設計 v0.1.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-002 品質ワークスペースおよび再発防止台帳の初期化

- **説明**: `quality-init` は、対象プロジェクトの `.spec/quality/` ディレクトリ構造（`sessions`, `scorings`, `analyses`, `viewpoints`, `reports`, `rules`）と再発防止ルール台帳（`rules-ledger.md`）を安全に初期化・配備しなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_init.py` が実行された THEN システムは `.spec/quality/` 配下の必須サブディレクトリ群を漏れなく作成する SHALL
  - WHEN `rules-ledger.md` が未配備である THEN システムは 初期ルールを含む台帳ファイルを新規作成する SHALL
  - WHEN すでに初期化済みのファイル・ディレクトリが存在する THEN システムは 既存内容を上書き・破壊せずスキップする SHALL
  - WHEN `--dry-run` オプションが指定された THEN システムは 実際のファイル書き込みを行わず作成予定の項目を表示する SHALL
- **検証手段**: tests/test_quality_init.py（ディレクトリ生成・既存保護・dry-run）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票 (br7.hide)
  - 1.0 (2026-08-14) 人間裁定・多観点レビュー（QLT-REV-001 PASS）により approved 化 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_init.py 全 PASS により verified 化 (br7.hide)
