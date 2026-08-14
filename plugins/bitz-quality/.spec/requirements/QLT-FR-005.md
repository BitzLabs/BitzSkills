---
id: QLT-FR-005
version: 1.0
status: verified
domain: quality-gate
priority: high
origin: アルダグラム3層品質ゲート + 設計 v0.1.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-005 静的チェック（S01〜S10）の自動実行と合否判定

- **説明**: `quality-gate` は、コミット・PR受入時に第1層の静的チェック（S01〜S10: 差分有無・デバッグ文残存・シークレット混入・台帳確認等）を自動実行し、欠陥のある変更をブロックしなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_gate.py` が実行された THEN システムは 差分ファイル内のデバッグキーワード（debugger, binding.pry等）およびAPIキー等のシークレットを検出する SHALL
  - WHEN 禁止キーワードまたはシークレットが検出された THEN システムは 不合格メッセージを出力し 非ゼロ終了する SHALL
  - WHEN `--staged` オプションが指定された THEN システムは ステージングされた変更（`git diff --cached`）のみを対象として検証する SHALL
  - WHEN 違反が0件の場合 THEN システムは ゼロ終了コード (0) を返し ゲート通過 (PASS) とする SHALL
- **検証手段**: tests/test_quality_gate.py（クリーン変更PASS、デバッグ文検知FAIL、シークレット検知FAIL）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票 (br7.hide)
  - 1.0 (2026-08-14) 人間裁定・多観点レビュー（QLT-REV-001 PASS）により approved 化 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_gate.py 全 PASS により verified 化 (br7.hide)
