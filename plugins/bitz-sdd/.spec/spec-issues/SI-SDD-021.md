---
id: SI-SDD-021
raised_by: SI-CORE-018（表示層日本語化）の実装中に発見（2026-07-21）
target: plugins/bitz-sdd/skills/sdd-report/scripts/sdd_report.py のタスク status 集計語彙
proposed_change_type: modify
status: open
---
- **優先度（推薦）**: **中**。`blocked` タスクの取りこぼしという実害があるが、
  SI-CORE-018 の表示層日本語化とは独立に修正でき、ブロック関係にはない。
- **目的**: `sdd_report.py` のタスク status 集計語彙が正規語彙と食い違っている。整合させる。
  - **集計キーが正規語彙でない**: `sdd_report.py` は `task_stats = {"todo", "doing", "done"}`
    で集計するが、`spec_update.py` の権限マトリクス `TRANSITIONS["task"]` が定める正規語彙は
    `pending` / `implementing` / `blocked` / `done` である。`spec_status.py` は正規語彙で
    集計しており、同じ `.spec/tasks/` を見る2つのツールが別の語彙で報告している。
  - **`blocked` が不可視になる（実害）**: 語彙外の status は `else` 分岐で `todo` に加算される
    ため、`status: blocked` のタスクは「Todo」に混ざり、レポート上で存在が消える。
    `sdd-plan` の責務には「blocked の理由を特定して提示する」ことが含まれる（SDD-FR-120）が、
    人間向けレポートである status-report からはブロック中のタスクが読み取れない。
  - `implementing` も同様に `todo` へ吸収され、実装中のタスクが未着手として報告される。
- **提案する修正**:
  1. `task_stats` の集計キーを正規語彙（`pending` / `implementing` / `blocked` / `done`）に改める。
  2. 語彙外の status を `todo` へ黙って吸収せず、`(none)` 等の独立した区分として可視化する
     （`spec_status.py` の `_statuses_in` が `(none)` を立てる挙動に揃える）。
  3. 表示は SI-CORE-018 の対訳方針に従い日本語主の併記形にする
     （`spec_labels.py` の `status_label("task", ...)` を用いる）。
  4. 回帰テストを先行追加する（`blocked` / `implementing` のタスクが独立して計上されること、
     語彙外 status が `pending` に混入しないこと）。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-report/scripts/sdd_report.py`、
  `tests/test_sdd_report.py`、bitz-sdd の3マニフェスト。
- **確認観点**:
  - `spec_status.py` と `sdd_report.py` が同じ `.spec/tasks/` に対して同じ内訳を報告すること
  - `blocked` / `implementing` のタスクが独立した区分として現れること
  - `.venv/bin/pytest` / `spec inspect --workspace . plugins/*` / `release_check.py` が PASS
- **影響推定・ロールバック**: `.spec/reports/status-report.md` の表示内容のみが変わり、
  `.spec/` の frontmatter 移行は不要。集計ロジックの変更であるため件数の内訳が変わる
  （これが修正の目的）。ロールバックは `sdd_report.py` とテストの revert で戻る。
- **依存**: なし。SI-CORE-018 とは独立に実施できる。
  修正3（日本語併記）のみ SI-CORE-018 の `spec_labels.py` 導入後に実施する必要がある。
- **可否の予備判定（推薦）**: **accept 推薦**。根拠:
  - 既存要件との矛盾: なし。SDD-FR-120（sdd-plan の blocked 提示）を充足する方向の修正
  - ガードレール抵触: なし
  - 影響範囲: `sdd_report.py` の集計部とそのテストに閉じる
  - 軽量レーン適否: **可**。公開契約（`.spec` スキーマ・frontmatter 書式）に触れず、
    `status-report.md` の表示内容に閉じるため
