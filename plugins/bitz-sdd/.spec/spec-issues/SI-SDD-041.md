---
id: SI-SDD-041
raised_by: bitz-flow M2 差分レビュー時の実装者（claude）
target: sdd-core の spec_scaffold.py・sdd-review の SKILL.md
proposed_change_type: new
status: accepted
---
- **目的**: レビュー統合成果物にも**採番付き雛形**を用意し、必須キーの取りこぼしを
  「書いた後に検証で弾かれる」のではなく「最初から入っている」状態にする。

- **現状（生成と検証の非対称）**:

  | 成果物 | 生成支援 | 機械検証 |
  |---|---|---|
  | requirement / task / spec-issue / design / gate | `spec scaffold` が必須キー入りの雛形を出す | `spec_inspect` |
  | **review（統合レビュー）** | **無い** | `spec_inspect`（`SDD-FR-158` / `SDD-FR-161`） |

  - `spec_scaffold.py` の種別は `{design, gate, requirement, spec-issue, task}` で **review が無い**
  - `sdd-review` に `scripts/` が存在しない（`SKILL.md` / `assets` / `references` のみ）
  - schema の正は `references/synthesis.md` に**散文として**書かれているだけ

  他の成果物は scaffold が雛形を出すので必須キーを落としようがない。
  **レビューだけ手書きで、検証は厳格なのに生成が素手**という状態にある。

- **実際に起きた事故**（2026-08-12、bitz-flow `FLW-REV-011` の作成時）:

  | 誤り | `spec_inspect` の指摘 |
  |---|---|
  | `findings[]` に `severity` / `source` / `recommendation` / `status` を書かなかった | 84 件（21 findings × 4 キー） |
  | `gate_preconditions[].id` を完全 ID（`FLW-REV-011:GP-001`）で書いた（正は `GP-001`） | 18 件の幽霊参照 |
  | `basis: verified` に `evidence` を付けなかった | 5 件 |
  | 最新ビュー `review-synthesis.json` に `review_id` を置かなかった | 1 件 |

  合計 111 問題。**検証層は正しく機能した**が、手戻りがすべて「書いた後」に発生した。
  3 往復して修正しており、雛形があれば 0 往復で済んだ。

- **提案する修正**:

  1. `spec_scaffold.py` へ **`review` 種別**を追加する。
     `python3 <sdd-core スキル>/scripts/spec_scaffold.py <ws> review --prefix <REV接頭辞>` で
     `<REV-ID>.json` と `<REV-ID>.md` を採番付きで生成する。
  2. JSON 雛形は `SDD-FR-158` / `SDD-FR-161` の必須キーをすべて含む。
     - `findings[]` は既定 0 件（空配列）。`--findings N` で N 件の雛形を出せる。
       雛形の finding は `id` / `priority` / `severity` / `source` / `title` /
       `recommendation` / `tracked_by` / `status` をすべて持つ。
     - `gate_preconditions[]` も同様に `--preconditions N` で雛形を出し、
       `id` は `GP-NNN`（レビュー ID を含めない）形式で採番する。
     - `basis: verified` の雛形には `evidence` キーを空文字で置く（書き忘れではなく
       「埋めるべき欄」として見えるようにする）。
  3. Markdown 雛形は frontmatter（`id` / `title` / `status` / `version` / `updated` /
     `owner` / **`decision`**）と、観点別スコア表・findings 表・Gate 前提条件表の骨格を持つ。
  4. `sdd-review` の SKILL.md へ「統合判定の成果物は scaffold で作る」を手順として書く。

- **対象ファイル**:
  - `plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py`
  - `plugins/bitz-sdd/skills/sdd-review/SKILL.md`
  - `tests/test_spec_scaffold.py`（無ければ新設）

- **確認観点**: 生成した雛形が**そのまま** `spec_inspect` を通ること（必須キーの欠落 0）。
  `--findings N` / `--preconditions N` で出した雛形も通ること。
  採番が既存の `<REV-ID>` と衝突しないこと。既存4種別の生成が壊れないこと。

- **影響推定・ロールバック**: 種別の**追加**であり既存の生成物を変えない。
  ロールバックは追加分を除くだけで足りる。

- **V4 との関係**: V4 の13テーマを確認したが該当するものは無い。
  テーマ3「レビュー品質目標の引き上げ」はスコア基準の話、
  テーマ13「検証活動の成果物化」は測定定義・計測器・検証履歴のモデル化であり、
  **レビュー成果物の書きやすさは両方の対象外**。V4 を待つ性質ではなく V3 系で足せる。
