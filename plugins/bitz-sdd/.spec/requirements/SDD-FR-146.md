---
id: SDD-FR-146
version: 1.0
status: implementing
domain: verification
priority: medium
origin: SI-SDD-014
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-146 canonical実行時のworkspace横断テスト参照集約

- **説明**: モノリポでは各パッケージの `.spec/` が独立ワークスペースになる一方、
  テストはリポジトリルートの `tests/` に集約されることがある。この配置では
  ワークスペース配下だけを走査する参照判定が、実際にはテストが存在する要件を
  「テスト/実装からの参照がない」と誤報する。複数ワークスペースを同時に検査する
  canonical 実行（`--workspace . plugins/*`）に限り、全入力ワークスペースの
  テスト・実装参照をグローバル ID で集約し、その ID を所有するワークスペースの
  未参照判定へ還流する。単一ワークスペース検査の結果は変えない。
- **受入基準 (EARS)**:
  - WHEN 複数ワークスペースを同時に検査し、あるワークスペースのテストが別ワークスペースの要件 ID を参照している THEN 当該要件を未参照として報告しないこと SHALL
  - WHEN 単一ワークスペースだけを検査する THEN 集約を行わず、当該ワークスペース配下の参照だけで未参照を判定すること SHALL
  - WHEN 集約により未参照でなくなった要件をレポートへ表示する THEN 参照元のワークスペース名と相対パスを識別できる形で示すこと SHALL
  - WHEN どのワークスペースからも参照されていない要件がある THEN 従来どおり未参照として報告すること SHALL
  - WHILE 集約が有効な間 THE `spec_inspect.py` は幽霊参照・孤児要件・実装待ちの各判定と PASS / FAIL 判定を変更しないこと SHALL
- **検証手段**: tests/test_spec_inspect.py の unit-test で、(1) ルート tests が
  プラグイン要件を参照する fixture で当該要件が未参照リストから消えること、(2) 同じ
  fixture を単一ワークスペースで検査すると未参照のままであること、(3) どこからも
  参照されない要件が未参照に残ること、(4) 集約が幽霊参照判定と終了コードを変えないことを検証する。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-014 から導出、Design Gate の論点1（案A）を実装する。
