---
id: SDD-FR-139
version: 1.0
status: verified
domain: workflow
priority: medium
origin: SI-SDD-021（sdd-report のタスク集計語彙が正規語彙と乖離）
verification_method: unit-test
derived_from: SDD-FR-137
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-139 sdd_report のタスク集計を正規語彙へ整合し日本語表示する

- **説明**: `sdd_report.py` のタスク status 集計が独自語彙（`todo` / `doing` / `done`）を用いており、
  `spec_update.py` の権限マトリクス `TRANSITIONS["task"]` および `spec_labels.py` が定める正規語彙
  （`pending` / `implementing` / `blocked` / `done`）と食い違っている。語彙外の status を暗黙に
  `todo` へ吸収するため、`blocked`（介入待ち）や `implementing`（実装中）のタスクが人間向けレポート
  status-report.md 上で「Todo」に紛れて不可視になる（実害）。同じ `.spec/tasks/` を見る
  `spec_status.py` と `sdd_report.py` が別語彙で報告する不整合を解消する。集計語彙を正規化した上で、
  SDD-FR-137 が本要件へ後送りしていた日本語表示（`spec_labels.py` の対訳による日本語主併記）を適用する。

- **受入基準 (EARS)**:
  - THE `sdd_report.py` のタスク集計は正規語彙（`pending` / `implementing` / `blocked` / `done`）を集計キーに用いる SHALL
  - WHEN タスクの status が正規語彙のいずれかであるとき THEN 当該語彙の区分として計上する SHALL
  - WHEN タスクの status が正規語彙外（欠落・空・未知の値）であるとき THEN `todo` 等の正規区分へ黙って吸収せず、`(none)` 等の独立区分として可視化する SHALL（`spec_status.py` の `_statuses_in` が語彙外を `(none)` として立てる挙動に揃える）
  - WHEN タスク集計を表示するとき THEN `spec_labels.py` の `status_label("task", ...)` を用いて日本語主の併記形（例: `介入待ち（blocked）`）で表示する SHALL
  - THE 本要件の変更は `sdd_report.py` の集計ロジックと status-report.md の表示に限られ、`.spec/` 配下 frontmatter の `status` 機械値を一切変更しない SHALL

- **検証手段**: `tests/test_sdd_report.py` に回帰テストを先行追加し `.venv/bin/pytest` で検証する。
  ①`status: blocked` と `status: implementing` のタスクが独立した区分として計上され「Todo」に吸収されないこと
  ②正規語彙外の status（欠落・未知値）が正規区分へ混入せず独立区分（`(none)` 等）で可視化されること
  ③タスク集計の表示が `status_label("task", ...)` 由来の日本語主併記形であること。
  加えて `spec inspect --workspace . plugins/*` / `release_check.py` が PASS を維持する。

- **Revision History**:
  - 1.0 (2026-07-22) 初版（draft 起票）。SI-SDD-021 を要件化。SDD-FR-137 が後送りした集計語彙修正＋日本語表示を担う。
