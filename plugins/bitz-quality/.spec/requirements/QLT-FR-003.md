---
id: QLT-FR-003
version: 1.0
status: verified
domain: quality-doctor
priority: high
origin: 環境診断設計 v0.1.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-003 品質環境・ルール台帳・セッション健全性の読み取り専用診断

- **説明**: `quality-doctor` は、プロジェクトの `.spec/quality/` ディレクトリ構造、再発防止ルール台帳、進行中セッションの健全性を読み取り専用で診断し、問題があれば修復手順を報告しなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_doctor.py` が実行された THEN システムは ディレクトリ実在・台帳実在・セッション構文を読み取り専用で検査する SHALL
  - WHEN 必須サブディレクトリまたは台帳が欠落している THEN システムは 警告メッセージと `quality-init` による修復案内を出力し 非ゼロ終了する SHALL
  - WHEN すべてのチェックを通過した THEN システムは ゼロ終了コード (0) と健全サマリーを出力する SHALL
- **検証手段**: tests/test_quality_doctor.py（正常系・欠落系・破損JSON系）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票 (br7.hide)
  - 1.0 (2026-08-14) 人間裁定・多観点レビュー（QLT-REV-001 PASS）により approved 化 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_doctor.py 全 PASS により verified 化 (br7.hide)
