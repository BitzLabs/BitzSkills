---
id: SDD-FR-166
version: 1.0
status: implementing
domain: workflow
priority: medium
origin: SI-SDD-040
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-166 verified要件の再着手（verified → implementing）

- **説明**: verified になった要件の適用範囲が後続の作業で広がったとき、検証証跡を壊さずに
  実装へ結び付けられるようにする。ただし機械が verified を勝手に取り消せないよう、
  人間裁定必須の遷移として扱う。
- **受入基準 (EARS)**:
  - WHEN 要件の status を verified から implementing へ遷移させる THEN spec_update は当該遷移を受理すること SHALL
  - WHEN verified から implementing への遷移を人間裁定経路（--interactive-decision または --on-behalf-of）なしで要求する THEN spec_update は対象と STATE を変更せず authorization-required で終了すること SHALL
  - WHEN verified から implementing への遷移を代行可視化経路で行う THEN spec_update は --decision-ref を必須とし、STATE へ provenance と裁定参照を記録すること SHALL
  - WHEN 要件が verified から implementing へ戻る THEN spec_update は .spec/verification/ の既存検証証跡を削除も改変もしないこと SHALL
  - WHEN promoted から implementing への遷移を要求する THEN spec_update は precondition-failed として拒否すること SHALL
- **検証手段**: 遷移の受理・人間裁定経路なしでの拒否・裁定参照の必須性・検証証跡の非改変・
  promoted からの戻りの拒否を unit-test で検証する。
- **Revision History**:
  - 1.0 (2026-08-12) SI-SDD-040（bitz-flow SI-FLW-040 の委託）を受けて draft 起票
