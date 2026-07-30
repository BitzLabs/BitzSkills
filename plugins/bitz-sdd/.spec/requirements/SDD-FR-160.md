---
id: SDD-FR-160
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-SDD-031
verification_method: unit-test
derived_from: SDD-FR-158
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-160 レビュー成果物のアーカイブを強制し未消化指摘を持ち越す

- **説明**: `review-synthesis.json` は最新1件で上書きされ、番号付きファイルへの退避は
  「次のレビューを記録するコミットで前回分を追加する」という**手作業に依存した工程**だった。
  git 履歴には残るが、次のレビュー作成者がこの手順を飛ばせば `.spec/` を正とする規律の外に出る
  （SI-SDD-031）。本要件はアーカイブを機械的に強制し、未消化の P0/P1 を次のレビューへ
  持ち越す。実装は **`review-synthesis.*` のビュー化が先行する** —— 自前の ID を持ったまま
  番号付きファイルへ複写すると既存の重複 ID 検査が正しく発火して FAIL するため、
  ビュー化しなければアーカイブできない。設計の正は SDD-DSN-011。
- **受入基準 (EARS)**:
  - WHEN レビューを記録する THEN `.spec/reviews/<REV-ID>.json` として保存することを必須とし、`review-synthesis.json` は最新へのビューと位置づけて自前の成果物 ID を持たせないこと SHALL
  - WHEN `spec inspect` が `review-synthesis.json` を検査する THEN その `review_id` に対応する `<REV-ID>.json` が存在しないことをアーカイブ漏れとして不整合に報告すること SHALL
  - WHEN `review-synthesis.json` と番号付きファイルが併存する THEN 同一 ID の重複を不整合として報告しないこと SHALL
  - WHEN 新しい synthesis を生成する THEN 過去の全 `<REV-ID>.json` から `status` が `resolved` でない `P0`/`P1` の finding を `carried_over[]` として取り込むこと SHALL
  - WHEN `carried_over[]` の各要素を検査する THEN 取り込み元の finding ID が実在することを検査し、不在を幽霊参照として報告すること SHALL
  - WHEN `schema_version` を持たない既存レビューを検査する THEN アーカイブ漏れ検査の対象に含めるが、`carried_over[]` の欠落は不整合としないこと SHALL
- **検証手段**: `tests/test_spec_inspect.py`（アーカイブ漏れの検出、ビュー化後に重複 ID が
  出ないこと、`carried_over[]` の幽霊参照）と `sdd-review` の `references/synthesis.md` の
  手順記述の機械確認で unit-test する。導入直後に実測ワークスペースで検出される件数が
  設計の想定と一致することを確認する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-031 提案3 と
    SDD-DSN-011 の実装順序1・2 から導出。
