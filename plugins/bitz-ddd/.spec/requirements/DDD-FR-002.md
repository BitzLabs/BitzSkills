---
id: DDD-FR-002
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-018（ルート .spec/spec-issues/。ルート→サブ委任）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### DDD-FR-002 成熟度レベル・MMI 採点表の表示日本語化

- **説明**: SI-CORE-018 の対訳方針（機械値は英語のまま維持し表示層だけを日本語化する）を
  bitz-ddd にも適用する。対象は `ddd-evaluate` の DDD 成熟度レベルと MMI（Modularity
  Maturity Index）4軸の採点表で、いずれもスクリプトを持たない文書成果物
  （`SKILL.md` / `references/ddd-maturity.md` / `references/mmi-maturity.md` /
  `assets/evaluation-scorecard.md`）である。

  bitz-ddd は bitz-sdd への依存を宣言しているが、AGENTS.md のスキル自己完結原則により
  sdd-core の `spec_labels.py` を相対参照しない。本要件の対象語彙（成熟度レベル・MMI 軸名）は
  SDD-FR-137 の対訳辞書が扱う SDD ライフサイクル語彙とは別体系であり、辞書を共有しない。

- **受入基準 (EARS)**:
  - THE `ddd-evaluate` の成熟度レベルと MMI 4軸（Cohesion / Coupling / Independence / Reusability）の表示は SI-CORE-018 の対訳方針に従い日本語を併記する SHALL
  - THE 併記の語順は評価軸名・レベル名ともに英語主（例: `Cohesion（凝集度）`）とする SHALL（フェーズ名と同じく評価枠組みの固有名詞であり、原典（DDD / MMI）の用語で参照されるため）
  - THE 採点結果として記録される機械可読な値（レベル番号・スコア）は変更しない SHALL（表示層のみの変更であること）
  - THE bitz-ddd は sdd-core の `spec_labels.py` を相対パスで参照せず、自プラグイン内で完結する SHALL（AGENTS.md のスキル自己完結原則）

- **検証手段**: skill-validator チェックリスト PASS + `python3 scripts/release_check.py` PASS +
  対象4ファイル（`SKILL.md` / `references/ddd-maturity.md` / `references/mmi-maturity.md` /
  `assets/evaluation-scorecard.md`）の目視確認により、①全レベル名・全軸名に日本語が併記されて
  いること ②語順が英語主であること ③レベル番号・スコアの表記に diff が無いこと を確認する。

- **Revision History**:
  - 1.0 (2026-07-21) 初版（draft 起票）
