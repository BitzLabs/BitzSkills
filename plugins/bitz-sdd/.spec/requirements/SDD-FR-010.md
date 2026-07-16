---
id: SDD-FR-010
version: 1.0
status: verified
domain: verification
priority: high
origin: skills/sdd-core/SKILL.md v1.7.3（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-010 構造検証スクリプトによる整合性検証とレポート出力

- **説明**: プロジェクトの整合性を保つため、`spec_inspect.py` は指定されたワークスペース内の要件、設計、タスクの整合性を走査・検証し、結果をレポートとして出力しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN プロジェクトルートを引数に指定して `spec_inspect.py` を実行する THEN システムは `.spec/` 配下の要件、設計、タスクの整合性を検証し、検証結果を `.spec/inspection-report.md` に出力する SHALL
  - WHEN 整合性検証でエラー（存在しない要件IDやタスクIDへの参照など）が検出されない THEN `spec_inspect.py` は終了コード 0 で正常終了する SHALL
  - WHEN 整合性検証でエラーが検出された THEN `spec_inspect.py` は終了コード 1 で異常終了する SHALL
- **検証手段**: tests/test_spec_inspect.py
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
