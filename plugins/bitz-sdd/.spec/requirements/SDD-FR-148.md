---
id: SDD-FR-148
version: 1.0
status: verified
domain: verification
priority: medium
origin: SI-SDD-014
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-148 manual-check要件の未参照報告分離

- **説明**: `verification_method: manual-check` の要件は、検証手段が目視確認や
  チェックリスト通過であり、テストコードから ID を参照されることが原理的にない。
  これらを自動検証要件と同じ「テスト/実装からの参照がない要件」へ並べると、
  真のトレース欠落が manual-check 要件に埋もれる。未参照の報告を
  「自動検証要件の未参照」と「manual-check 要件の未参照」の2つの見出しへ分離し、
  後者には検証記録で担保される旨を添える。manual-check であることを理由に
  報告そのものから除外はしない。
- **受入基準 (EARS)**:
  - WHEN 未参照の要件に自動検証手段（manual-check 以外）のものが含まれる THEN それらを自動検証要件の未参照として列挙すること SHALL
  - WHEN 未参照の要件に `verification_method: manual-check` のものが含まれる THEN それらを manual-check 専用の見出しへ分けて列挙すること SHALL
  - WHEN manual-check の要件を分離して列挙する THEN 検証記録で担保される旨の注記を添えること SHALL
  - WHILE 分離報告が有効な間 THE `spec_inspect.py` は未参照の検出そのものを取りやめず、また PASS / FAIL 判定を変更しないこと SHALL
- **検証手段**: tests/test_spec_inspect.py の unit-test で、(1) manual-check 要件が
  自動検証要件の未参照リストに現れないこと、(2) manual-check 専用見出しへ列挙されること、
  (3) 自動検証要件が従来どおり列挙されること、(4) 分離の前後で終了コードが変わらないことを検証する。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-014 から導出、Design Gate の論点3を実装する。
