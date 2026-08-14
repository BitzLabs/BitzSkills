---
id: QLT-FR-009
version: 1.0
status: verified
domain: quality-review
priority: high
origin: アルダグラム3層ゲート（第2層LLMレビュー）+ 設計 v0.3.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-009 LLM多観点レビュー（L01〜L11）の自律実行と指摘抽出

- **説明**: `quality-review` は、変更差分に対して読み取り専用のLLM多観点レビュー（L01〜L11: 仕様適合・境界値・エラー処理・セキュリティ・可読性等）を実行し、P0〜P3の重要度付き指摘事項を構造化抽出できなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_llm_review.py` が実行された THEN システムは 差分ファイルに対して各観点（L01〜L11）の評価プロンプト・チェックロジックを適用する SHALL
  - WHEN 重大な指摘 (P0/P1) が検出された THEN システムは 判定結果を FAIL とし 指摘一覧を出力する SHALL
  - WHEN 指摘が軽微 (P2/P3) または 0件の場合 THEN システムは 判定結果を PASS または CONDITIONAL_PASS とする SHALL
- **検証手段**: tests/test_quality_review.py（正常系PASS、P0/P1指摘検知FAIL、観点網羅）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票・承認 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_review.py 全 PASS により verified 化 (br7.hide)
