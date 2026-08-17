---
id: FLW-CON-007
version: 1.0
status: approved
domain: governance
priority: high
origin: SI-FLW-072
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-CON-007 契約語彙の単一の正と機械照合

- **説明**: 公開 result・公開 schema・実装に現れる closed enum の値集合を、設計の閉集合表を
  唯一の正として三者（設計・schema・実装定数）で双方向に照合し、照合対象の欠落そのものを
  検出する。M2 出口条件4「enum三者照合テストがgreen」に対応する要件が存在せず、
  照合が宣言された全 namespace ではなく一部しか回っていなかったことによる
  （`FLW-REV-019`。`quarantined` が実装定数にだけ追加され公開 schema へ入らないまま
  公開経路へ出た）。規範は `FLW-DSN-016` §2。
- **受入基準 (EARS)**:
  - WHEN closed enum の値集合を検査する THEN bitz-flowは設計の閉集合表を唯一の正とし、値の正を他文書へ委譲する行を持たないこと SHALL
  - WHEN 三者照合を実行する THEN bitz-flowは設計の閉集合表から得た全namespaceを対象とし、対象を実装側が解決できたnamespaceに限定しないこと SHALL
  - WHEN 三者照合を実行する THEN bitz-flowは設計 ⊆ schema と schema ⊆ 設計の双方向、および設計 ⊆ 実装定数と実装定数 ⊆ 設計の双方向を検査すること SHALL
  - WHEN あるnamespaceの実装定数の所在が宣言されていない THEN bitz-flowは当該namespaceをskipせず不合格として報告すること SHALL
  - WHEN あるnamespaceの値が公開resultに現れる THEN bitz-flowは当該namespaceに対応する公開schemaの定義が存在しない限り合格を返さないこと SHALL
  - WHEN 同一namespaceが複数のschemaに現れる THEN bitz-flowは全出現を照合対象とし、schema間の不一致を不合格として報告すること SHALL
  - WHEN 1つのnamespaceに対する実装定数が集合として1箇所に存在しない THEN bitz-flowは照合不能として不合格を報告すること SHALL
  - WHEN 設計の閉集合表・実装定数の所在表・実際に照合したnamespaceの3集合を比較する THEN bitz-flowは3集合が完全一致しない場合に不合格を報告すること SHALL
  - WHEN 複数namespaceに現れる値の一覧を提示する THEN bitz-flowは閉集合表から機械導出した結果と設計文書の生成区間が一致しない場合に不合格を報告すること SHALL
  - WHEN 複数namespaceに現れる値を判定する THEN bitz-flowは値の比較をcase-sensitiveで行うこと SHALL
- **検証手段**: 閉集合表をパースして全namespaceを解決し、schema の `$defs` と実装定数を
  双方向に突き合わせる unit test で検証する。所在未宣言のnamespace、公開resultに現れるが
  schema定義が無いnamespace、schema間不一致、3集合の不一致、生成区間の不一致のそれぞれに
  陽性対照を置き、意図的に壊した入力で必ず FAIL することを確認する。
- **Revision History**:
  - 1.0 (2026-08-17) accepted `SI-FLW-072` と `FLW-DSN-016` §2 から draft 起票。
    M2 出口条件4に対応する要件が存在しなかった欠落を埋める
    （従来 `FLW-DSN-014` の対応表は `FLW-CON-006` を指していたが、同要件は
    破壊操作とcleanupの安全境界のみを扱い enum 照合の受入基準を持たない）
