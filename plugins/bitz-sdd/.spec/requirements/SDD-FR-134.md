---
id: SDD-FR-134
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-SDD-017
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-134 approved要件の孤児判定を警告へ分離

- **説明**: 要件化PRを先に反映し、実装タスクを後続PRで起票する推奨フローを成立させるため、
  `approved` かつ実装タスク未紐付けの要件を「実装待ち」の警告として報告し、孤児要件FAILから
  分離する。`implementing` 以降でタスクがない不整合は従来どおりFAILとする。
- **受入基準 (EARS)**:
  - WHEN `approved` 要件に `implements` するタスクが存在しない THEN `spec_inspect.py` はその要件を実装待ち警告としてレポートへ列挙し、その事実だけではFAILにしないこと SHALL
  - WHEN `implementing`、`verified`、または`promoted`要件に `implements` するタスクが存在しない THEN `spec_inspect.py` はその要件を孤児要件として列挙しFAILすること SHALL
  - WHEN `approved` 要件に `implements` するタスクが存在する THEN 実装待ち警告へ列挙しないこと SHALL
  - WHILE 既存の問題・幽霊参照・孤児要件が存在する間 THE `spec_inspect.py` は従来どおりFAIL判定を維持すること SHALL
- **検証手段**: tests/test_spec_inspect.py の unit-test で、approved未紐付けのWARN/PASS、
  implementing以降の未紐付けFAIL、approved紐付け済みの非警告を検証する。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（SI-SDD-017 のユーザー採用裁定・推奨案1を受けて起票）
