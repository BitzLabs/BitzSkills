---
id: SI-SDD-034
raised_by: bitz-flow v2再設計の振り返り（GitHub Issue #123）
target: spec_status.pyの完了済み要件とdraft要件併存時のフェーズ判定
proposed_change_type: modify
status: accepted
github_issue: https://github.com/BitzLabs/BitzSkills/issues/123
---
- **目的**: `spec_status.py` の `determine_phase()` は、完了済みの要件・タスク群と新しい
  `draft` 要件群が同じ workspace に併存すると、未承認要件が残っていても
  `phase_code: done`（Promotion Gate 待ち）を返す。bitz-flow v2 再設計では、
  requirements が `draft: 17 / verified: 2`、tasks が `done: 4` の状態で
  `Done（確定待ち: Promotion Gate）` と判定される一方、`next_actions` は
  「draft 要件が17件 — 承認を行う」と表示した。フェーズ表示と次アクションが矛盾し、
  エージェントが Plan 工程を飛ばして Promotion Gate へ進むおそれがある。
- **原因**: 現在の `determine_phase()` は `n_appr`、`n_ver`、`n_tasks`、`n_done` を使い、
  `n_appr == 0 or n_tasks == 0` の場合だけ `plan` とする。旧系列の `verified` 要件が
  1件以上あり、旧タスクがすべて `done` なら、新系列の `draft` 要件が存在しても
  `n_ver == n_appr` と評価され、最終分岐で `done` になる。
- **提案する修正**:
  1. `done` は未完了成果物が存在しない場合だけ返すという不変条件を定義する。
     少なくとも `draft` 要件が1件以上あれば `done` を抑止する
  2. 次の候補を Design Gate で比較し、後方互換と複数変更系列への拡張性から選定する:
     (a) `draft` を優先して既存の `plan` を返す、
     (b) feature・世代単位でフェーズを集計する、
     (c) 既存 `phase_code` を削除・改名せず複合状態を加算する
  3. `phase_code` と `next_actions` が異なる工程を示さない整合条件を定義する
  4. 完了済みベースラインへ新しい `draft` 要件を追加する回帰テストを置く
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py`、
  `plugins/bitz-sdd/skills/sdd-core/SKILL.md`、
  `plugins/bitz-sdd/skills/sdd-core/references/gates.md`、`tests/test_spec_status.py`、
  `tests/test_spec_labels.py`、SDD-FR-136 の改訂または後継要件、関連する設計成果物、
  bitz-sdd マニフェスト。
- **確認観点**:
  - `verified` 要件・`done` タスクに `draft` 要件を追加した状態が `done` にならないこと
  - `draft` 要件がない従来の完了状態は `done` を維持すること
  - `phase_code` と `next_actions` が同一の次工程を案内すること
  - 要件が `draft → approved → implementing → verified` と進む各段階でフェーズが
    意図した順序になること
  - `tests/test_spec_status.py` と `tests/test_spec_labels.py` を含む全テストが PASS すること
- **影響推定・ロールバック**: `phase_code` は JSON 出力の公開契約であり、フェーズ判定は
  エージェントのルーティングを変えるため軽量レーン不可・通常フロー + Design Gate 必須。
  `spec inspect --impact SDD-FR-136` の結果、直接影響は `tests/test_spec_status.py`、
  `tests/test_spec_labels.py`、`plugins/bitz-sdd/.spec/tasks/SDD-TSK-020.md` の3成果物。
  既存値を維持する加算的変更を優先し、問題時は判定順と追加テストの revert で現行挙動へ戻す。
- **依存**: SDD-FR-136（フェーズ語彙と `determine_phase()` の公開契約）、
  SDD-FR-137（フェーズ表示対訳）、SI-SDD-020（フェーズ語彙整合。実施済み）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | SDD-FR-136 の既存 `phase_code` 削除・改名禁止を維持して解決可能 |
| ガードレール抵触 | なし。読み取り専用の集計と表示契約の修正 |
| 影響範囲 | sdd-core のフェーズ判定・ルーティング・表示、関連テスト、公開JSON契約 |
| 軽量レーン適否 | 不適。公開契約とエージェントの工程選択に影響するため Design Gate 必須 |

**推薦: accept**。再設計・次期版の要件追加という通常の運用で再現し、誤ったGateへ誘導するため、
単なる表示上の問題ではない。ただし、修正方式は単一 `plan` への回帰だけで確定せず、
複数変更系列をどう表現するかを Design Gate で裁定する。

## 実施

2026-07-30 に **accept**。裁定記録は
`.spec/reports/decision-2026-07-30-order8-design-foundation.md`（裁定J）。
**加算的修正を V4 設計前に実施する**。bitz-sdd 自身が requirements 74件 verified /
tasks 50件 done の完了済みベースラインを持ち、V4 要件は draft として起票されるため、
本件は V4 設計中にそのまま踏む。

- **提案1**（`done` の不変条件）— 実装対象。「`done` は未完了成果物が存在しないときだけ返す」を
  定義し、少なくとも `draft` 要件が1件以上あれば `done` を抑止する。
- **提案2**（修正方式の選定）— **既存 `phase_code` を保ったままの加算（候補 (c) 相当）を採用**。
  `phase_code` の既存値は削除・改名しない（`SDD-FR-136` の公開契約を維持）。
  feature・世代単位の集計（候補 (b)）は V4 の Workspace 責任モデルと接する論点であり、
  いま構造を増やさない。
- **提案3**（`phase_code` と `next_actions` の整合条件）— 実装対象。
- **提案4**（完了済みベースラインへ `draft` を追加する回帰テスト）— 実装対象。
- 残余リスク: 公開契約（語彙）は維持するが、**同じワークスペースが返す `phase_code` の値は
  変わる**。`phase_code` を条件分岐に使っているスキル・スクリプトの棚卸しを実装時に行う。
