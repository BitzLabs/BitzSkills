---
id: SDD-FR-157
version: 1.0
status: approved
domain: workflow
priority: high
origin: SI-SDD-028
verification_method: unit-test
derived_from: SDD-FR-145
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-157 verified→promoted 遷移に GatePassage の参照を必須化する

- **説明**: `verified → promoted` は人間裁定必須遷移でありながら、遷移そのものに確認記録の欄が
  無く「誰が何を確認して昇格させたか」が残らなかった（SI-SDD-028 提案3）。本要件は
  promoted 遷移に GatePassage の参照を必須化し、代行可視化経路（SDD-FR-145）の担保を
  遷移の実行時点で強制する。**Gate の実行単位は「1 GatePassage = 1回の Gate 実行」**とし、
  対象は ID の集合を `scope` に明示列挙する — feature 単位に固定しない。bitz-sdd 自身のような
  逆起票ワークスペースには feature 境界が無く、63件はどの feature にも紐づかないためである。
  本規律は**導入後の遷移にのみ適用**し、既存の promoted 済み成果物へ遡及しない
  （「導入後の遷移に適用し既存へ証跡の遡及追加を要求しない」既存の前例に倣う）。
  設計の正は SDD-DSN-010（裁定 D3）。
- **受入基準 (EARS)**:
  - WHEN `verified → promoted` 遷移を要求した THEN `spec update` は `--gate-passage <GatePassage ID>` を必須とし、未指定の要求は対象成果物と STATE を変更せず非ゼロで終了すること SHALL
  - WHEN `--gate-passage` を受理する THEN 指定 ID の GatePassage が実在し `gate` が `promotion` であることを検査し、満たさない要求は変更せず非ゼロで終了すること SHALL
  - WHEN `--gate-passage` を受理する THEN 遷移対象の全 ID が当該 GatePassage の `scope` に列挙されていることを検査し、1件でも欠ける要求は変更せず非ゼロで終了すること SHALL
  - WHEN promoted 遷移を受理した THEN STATE の構造化 event へ参照した GatePassage の ID を記録し、`schema_version` の値は変更しないこと SHALL
  - WHEN `verified → promoted` 以外の遷移を要求した THEN `--gate-passage` を要求せず、従来どおりの認可経路のみで判定すること SHALL
  - WHEN 本規律の導入前に promoted へ到達済みの成果物を `spec inspect` が検査する THEN GatePassage 参照の不在を不整合として報告しないこと SHALL
  - WHEN `lifecycle.md` が `verified → promoted` を記述する THEN verified のまま滞留し続けることが正常状態でないことと、promoted 遷移が GatePassage を伴うことを明記すること SHALL
- **検証手段**: `tests/test_spec_update.py`（`--gate-passage` 欠落時の拒否と無変更、GatePassage の
  実在・`gate` 種別・`scope` 包含の検査、他遷移への非波及、STATE への記録）と
  `tests/test_spec_inspect.py`（既存 promoted の非遡及）で unit-test する。
  `lifecycle.md` の記述はマーカーによる文書検査で機械確認する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-028 提案3・4 と
    SDD-DSN-010 の Design Gate 裁定（D3）から導出。
