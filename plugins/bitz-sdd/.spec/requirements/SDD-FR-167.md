---
id: SDD-FR-167
version: 1.0
status: implementing
domain: workflow
priority: medium
origin: SI-SDD-041
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-167 レビュー統合成果物の採番付き雛形生成

- **説明**: レビュー統合成果物（`<REV-ID>.json` / `<REV-ID>.md`）にも採番付き雛形を用意し、
  `SDD-FR-158` / `SDD-FR-161` の必須キーを最初から満たした状態で書き始められるようにする。
  検証は既にあるが生成が無いという非対称を解消する。
- **受入基準 (EARS)**:
  - WHEN spec_scaffold に review 種別を指定する THEN spec_scaffold は接頭辞に基づく採番で `<REV-ID>.json` と `<REV-ID>.md` を生成すること SHALL
  - WHEN review 種別の雛形を生成する THEN spec_scaffold は findings[] と gate_preconditions[] を含む必須キーをすべて含む JSON を出力すること SHALL
  - WHEN 生成した雛形を spec_inspect が検査する THEN spec_inspect は必須キーの欠落を1件も報告しないこと SHALL
  - WHEN findings の件数を指定する THEN spec_scaffold は id・priority・severity・source・title・recommendation・tracked_by・status をすべて持つ finding 雛形を指定件数だけ出力すること SHALL
  - WHEN gate_preconditions の件数を指定する THEN spec_scaffold は id を GP-NNN 形式で採番し、basis が verified の雛形には evidence キーを置くこと SHALL
  - WHEN 既存の review 成果物がある workspace で採番する THEN spec_scaffold は既存の最大番号の次を採番し ID を衝突させないこと SHALL
  - WHEN review 以外の既存4種別を生成する THEN spec_scaffold は従来と同じ成果物を出力すること SHALL
- **検証手段**: 生成した雛形をそのまま spec_inspect にかけて必須キー欠落 0 を確認する
  unit-test で検証する。件数指定つきの雛形、採番衝突、既存種別の非退行も同時に検証する。
- **Revision History**:
  - 1.0 (2026-08-12) SI-SDD-041 を受けて draft 起票
