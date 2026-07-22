---
id: SDD-FR-140
version: 1.0
status: verified
domain: workflow
priority: medium
origin: SI-CORE-033（ルート .spec/spec-issues/。ルート→サブ委任）
verification_method: unit-test
derived_from: SDD-FR-136, SDD-FR-137
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-140 フェーズ正規語彙のコード⇔文書一致を機械検証する

- **説明**: フェーズの正規語彙（`spec_status.py` の `PHASE_CODES` — SDD-FR-136 が定める公開契約）が
  コードと文書に二重で存在し、一致が機械検証されていない。SDD-FR-137 条文6は
  「`sdd-core/SKILL.md` のフェーズ・ルーティング表と `references/gates.md` は `PHASE_CODES` が返す
  7語と同一の語彙を用いる」と定めたが、検証手段が目視のままで、実際に SI-SDD-020 で
  `Discuss`／`determine_phase()` の乖離が発生した。SDD-FR-137 の対訳辞書が採る
  「SSOT＋複製＋`release_check.py` による一致検証」の型を、フェーズ語彙の文書側へ拡張する。
  文書側には**機械抽出できる目印**（HTML コメントマーカー）を与え、自由文からの語推定に
  依らない（誤検出で検査が形骸化するのを防ぐ。目印形式は Design Gate で HTML コメントに裁定）。

- **受入基準 (EARS)**:
  - THE `sdd-core/SKILL.md` のフェーズ・ルーティング節と `references/gates.md` は、フェーズ正規語彙を宣言する HTML コメントマーカー `<!-- phase-vocabulary: <カンマ区切りの語> -->` を各1つ持つ SHALL
  - WHEN `scripts/release_check.py` を実行したとき THEN 各文書のマーカーから抽出した語の集合が `spec_status.py` の `PHASE_CODES`（7語）と過不足なく一致することを検証し、乖離があれば非ゼロ終了する SHALL
  - WHEN 文書のマーカー内の語を1つでも改竄・欠落・追加したとき THEN `release_check.py` は非ゼロ終了する SHALL（検査が実際に効くこと）
  - WHEN `PHASE_CODES` へ語を加算し、対応してマーカーも同じ語を加えたとき THEN `release_check.py` は FAIL しない SHALL（加算的変更を妨げないこと）
  - THE 検査は各文書に人間可読で併記された散文のフェーズ語リスト（バッククォートのスラッシュ区切り）ともマーカーの一致を境界付き文字列比較で検証し、可視リストの静かなドリフトも検出する SHALL（自由文からの語推定は行わない）
  - WHERE リポジトリに bitz-sdd プラグインが配置されていない THE 本検査は SKIP される SHALL（SDD-FR-137 の辞書検査と同じ扱い）
  - THE 本検査は status 語彙（`spec_update.py` の `TRANSITIONS` ⇔ `lifecycle.md`）を対象に含めない SHALL（範囲はフェーズ語彙に限定。status への拡張は後続 spec-issue で裁定する — SI-CORE-033 提案3）

- **検証手段**: `tests/test_release_check.py` に回帰テストを先行追加し `.venv/bin/pytest` で検証する。
  ①正しいマーカーで検査が PASS すること ②マーカー内の語を1つ改竄すると非ゼロ終了すること
  ③マーカーと `PHASE_CODES` の過不足（欠落・余剰）を検出すること ④可視の散文リストを改竄すると検出すること
  ⑤bitz-sdd 不在で SKIP されること。加えて `spec inspect --workspace . plugins/*` / `release_check.py` が PASS を維持する。

- **Revision History**:
  - 1.0 (2026-07-22) 初版（draft 起票）。SI-CORE-033 を要件化。SDD-FR-137 条文6 の目視検証を機械検証へ引き上げる。
