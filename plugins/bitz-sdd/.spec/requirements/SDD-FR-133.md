---
id: SDD-FR-133
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-SDD-018
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-133 spec_inspectの読み取り専用check-onlyモード

- **説明**: 並列PRやworktreeで検証を実行しても、各ワークスペースの
  `.spec/inspection-report.md` を生成・更新せず、通常検査と同じ判定と標準出力を得られる
  `spec_inspect.py --check-only` を提供する。既定動作は従来どおりレポートを書き込む。
- **受入基準 (EARS)**:
  - WHEN `--check-only` 付きで単一または複数ワークスペースを検査する THEN 通常検査と同一のレポート本文を標準出力へ出し、同一条件で同じ終了コードを返すこと SHALL
  - WHILE `--check-only` が指定されている間 THE `spec_inspect.py` は既存の `.spec/inspection-report.md` を変更せず、存在しない場合も新規作成しないこと SHALL
  - WHEN `--check-only` なしで検査する THEN 従来どおり各ワークスペースの `.spec/inspection-report.md` を生成または更新すること SHALL
  - IF `--check-only` 検査で問題・幽霊参照・孤児要件を検出した場合 THEN レポートを書き込まず終了コード1を返すこと SHALL
- **検証手段**: tests/test_spec_inspect.py の unit-test で、既存レポートのバイト不変、
  レポート不在時の非生成、通常モードとの標準出力・終了コード一致、FAIL時の非書き込みを検証する。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（SI-SDD-018 のユーザー採用裁定を受けて起票）
