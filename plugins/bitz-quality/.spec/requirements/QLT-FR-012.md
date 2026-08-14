---
id: QLT-FR-012
version: 1.0
status: verified
domain: quality-trace
priority: high
origin: bitz-sdd V4 契約接続 + 設計 v0.4.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-012 テスト実行結果からの検証証跡（verification evidence）自動生成と .spec 連携

- **説明**: `quality-trace` は、pytest の実行結果（JUnit XML / stdout）から各要件に対する検証証跡（`verification-evidence`）を抽出し、`.spec/quality/reports/verification-matrix.md` に自動出力・記録できなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_trace.py report` が実行された THEN システムは テスト合格件数・実行時間・各要件の判定結果を含む検証証跡Markdownを生成する SHALL
  - WHEN 要件のステータス遷移が必要な場合 THEN システムは `spec_update.py` と連携可能な証跡ログをフォーマット出力する SHALL
- **検証手段**: tests/test_quality_trace.py（証跡レポート生成、合格サマリー出力）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票・承認 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_trace.py 全 PASS により verified 化 (br7.hide)
