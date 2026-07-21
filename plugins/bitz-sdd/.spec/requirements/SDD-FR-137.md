---
id: SDD-FR-137
version: 1.1
status: verified
domain: workflow
priority: medium
origin: SI-CORE-018（ルート .spec/spec-issues/。ルート→サブ委任）
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-137 ライフサイクル語彙の対訳辞書と表示層の日本語化

- **説明**: 要件・spec-issue・タスクの status とワークフローのフェーズが英語の機械値でしか
  表示されず、人間が状態を直読できない。frontmatter の機械値は英語のまま維持したうえで、
  表示層だけを日本語化する（SI-CORE-018 の裁定。値の日本語化＝機械値移行は不採用）。

  対訳の正は sdd-core の `scripts/spec_labels.py` に閉じる。ただし AGENTS.md のスキル
  自己完結原則（他スキルのファイルを相対パスで参照しない）があり、`sdd_report.py` は
  sdd-core を import しない独立構成のため、sdd-report は同内容の複製を持ち、両者の一致を
  `scripts/release_check.py` が機械検証する構成とする（SI-CORE-018 の辞書配置裁定）。

- **受入基準 (EARS)**:
  - THE sdd-core は `scripts/spec_labels.py` に status とフェーズの対訳辞書を定義し、これをリポジトリ内の対訳の唯一の正（SSOT）とする SHALL
  - THE `spec_labels.py` の status 対訳は 要件（`draft`=起草中 / `approved`=承認済み / `implementing`=実装中 / `verified`=検証済み / `promoted`=確定 / `deprecated`=廃止）・spec-issue（`open`=裁定待ち / `accepted`=採用 / `rejected`=不採用 / `superseded`=統合済み）・タスク（`pending`=着手待ち / `implementing`=実装中 / `blocked`=介入待ち / `done`=完了）を過不足なく含む SHALL
  - THE `spec_labels.py` のフェーズ対訳は `spec_status.py` の `PHASE_CODES` 7語すべて（`map`=未着手 / `discovery`=企画 / `design`=設計 / `plan`=要件定義 / `execute`=実装 / `verify`=検証 / `done`=確定待ち）を含み、`PHASE_CODES` との過不足は機械検証で検出される SHALL
  - WHEN 要件・spec-issue の status を表示するとき THEN 日本語主の併記形（例: `採用（accepted）`）で表示する SHALL
  - WHERE `sdd_report.py` のタスク集計は正規語彙（`pending` / `implementing` / `blocked` / `done`）ではなく独自語彙（`todo` / `doing` / `done`）を用いている THE 当該箇所の日本語化は本要件の範囲外とし SI-SDD-021 の集計語彙修正後に行う SHALL（語彙が正規化される前に表示だけ翻訳すると誤った語彙を対訳表に固定してしまうため）
  - WHEN フェーズを表示するとき THEN 英語主の併記形（例: `Execute（実装）`）で表示する SHALL
  - WHEN `phase_code` が `done` と判定されたとき THEN 表示ラベルは訳語「確定待ち」に Gate 名を合成し Promotion Gate 待ちであることを示す SHALL（SDD-FR-136 の受入基準を維持するため）
  - THE sdd-report は自スキル配下に `spec_labels.py` の複製を持ち、sdd-core のファイルを相対パスで参照しない SHALL（AGENTS.md のスキル自己完結原則）
  - WHEN `scripts/release_check.py` を実行したとき THEN sdd-core と sdd-report の対訳辞書の内容一致を検証し、乖離があれば非ゼロ終了する SHALL
  - THE 本要件の変更は表示層に限られ、`.spec/` 配下 frontmatter の `status` 機械値および `phase_code` の値を一切変更しない SHALL

- **検証手段**: `tests/` に回帰テストを先行追加し `.venv/bin/pytest` で検証する。
  ①`spec_labels.py` の辞書が3種別の全 status と `PHASE_CODES` 7語を過不足なく含むこと
  ②status 表示が日本語主・フェーズ表示が英語主の併記形であること ③`done` のラベルが
  `Promotion Gate` を含むこと（SDD-FR-136 の既存テストが改変なしで PASS し続けること）
  ④sdd-core と sdd-report の辞書が完全一致すること ⑤辞書を意図的に食い違わせた状態で
  `release_check.py` が非ゼロ終了すること。加えて `spec inspect --workspace . plugins/*` の
  PASS と、`.spec/` 配下 frontmatter に diff が出ないことを確認する。

- **Revision History**:
  - 1.1 (2026-07-21) `sdd_report.py` のタスク集計語彙が正規語彙と食い違う既存不整合
    （SI-SDD-021 として起票）を発見したため、当該箇所の日本語化を範囲外とする条文を追加
  - 1.0 (2026-07-21) 初版（draft 起票）
