---
id: SDD-FR-150
version: 1.0
status: verified
domain: sync
priority: high
origin: SI-SDD-011
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-150 同期マッピングSSOTと文書側同期表の一致検証

- **説明**: 同期マッピングはスキル文書（`sdd-docs` / `sdd-discovery` の SKILL.md）と実装
  （`sdd_sync.py` の `DEFAULT_MAPPING`）に二重定義されており、片方だけを更新した乖離は
  SI-SDD-011 で実際に発生した。宣言だけを読んだ利用者が存在しない同期を期待することを防ぐため、
  `DEFAULT_MAPPING` を唯一の正とし、文書側の同期表との一致を機械検証する。検証は
  SDD-FR-140（フェーズ正規語彙）と同じ HTML コメントマーカー方式に揃え、マーカーと
  人間可読の同期表の双方を照合して可視表の静かなドリフトも検出する。
  併せて、同期の対応が 1:1 であること（SDD-FR-149 の前提）も機械検証する。
- **受入基準 (EARS)**:
  - WHEN `release_check.py` が実行されたとき THEN システムは `sdd_sync.py` の `DEFAULT_MAPPING` を同期マッピングの正として抽出する SHALL
  - IF 文書側の `sync-mapping` マーカーの対集合が `DEFAULT_MAPPING` と一致しない THEN システムは欠落と余剰を示して FAIL する SHALL
  - IF 文書側の人間可読な同期表に、マーカーの対と同一行で対応する記載が無い THEN システムは当該の対を示して FAIL する SHALL
  - IF 検証対象文書に `sync-mapping` マーカーが無い THEN システムは FAIL する SHALL
  - WHEN `sdd-discovery` の SKILL.md を検証するとき THEN システムは `DEFAULT_MAPPING` のうち `.spec/discovery/` を同期元とする部分集合とのみ照合する SHALL
  - IF `DEFAULT_MAPPING` の複数の同期元が同じ docs 文書を同期先とする THEN システムは重複する同期先を示して FAIL する SHALL
  - WHEN マッピングの追加が `DEFAULT_MAPPING`・マーカー・可読表で同時に行われたとき THEN システムは FAIL しない SHALL
  - IF リポジトリに bitz-sdd プラグインが存在しない THEN システムは本検証を SKIP し、他の検査結果に影響を与えない SHALL
- **検証手段**: `tests/test_release_check.py` の SDD-FR-150 unit-test で、マーカーの欠落・
  余剰・同期先改竄・可読表ドリフト・マーカー不在・discovery 範囲外の混入・1:N 定義・
  加算的変更・bitz-sdd 不在時 SKIP の各ケースについて終了コードと FAIL 行を検証する。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-011 の提案4から導出。
