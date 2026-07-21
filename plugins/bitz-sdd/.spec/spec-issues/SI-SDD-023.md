---
id: SI-SDD-023
raised_by: 2026-07-21 SI-CORE-018 完了後の振り返りで発見
target: plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py の遷移事前条件検査
proposed_change_type: modify
status: open
---
- **優先度（推薦）**: **高**。不正な状態が一度書き込まれてから後段で検出される構造のため、
  検出時には既に手戻り（遡及的な辻褄合わせ）が発生している。
- **目的**: `spec_update.py` は遷移の**権限（誰が）だけを検査し、前提（成立条件）を検査しない**。
  そのため定義上ありえない状態を書き込めてしまい、乖離は後段の `spec_inspect.py` まで発覚しない。
  - **実際に発生した事象（2026-07-21）**: SI-CORE-018 の実施で、実装タスクを1件も起票しないまま
    3要件を `approved → implementing → verified` まで遷移させた。`spec_update.py` は
    すべて成功を返し、後続の `spec inspect --workspace . plugins/*` で**孤児要件 FAIL**
    （PASS 7 → 5 ワークスペース）となって初めて判明した。既に遷移済みだったため、
    タスクを後から起票して `done` にするという遡及的な辻褄合わせが必要になった。
  - **構造的な原因**: `spec_update.py` が `task` に言及するのは遷移表のキーと
    `KIND_DIR` のディレクトリ名の2箇所だけで、要件の遷移時に `.spec/tasks/` を参照しない。
    `implementing`（＝実装中）が実装タスクゼロで成立してしまう。
  - `spec_inspect.py` の孤児要件検出は「implementing 以降なのに implements するタスクがない」で
    正しく機能しており、**検出そのものではなく検出の遅さ**が問題である。
- **提案する修正**:
  1. 要件の `approved → implementing` 遷移時に、当該要件を `implements` するタスクの存在を
     事前条件として検査する。存在しなければ非ゼロ終了し、`spec_scaffold.py task` の実行を促す。
  2. 要件の `implementing → verified` 遷移時に、`implements` するタスクがすべて `done` で
     あることを検査する（未完了タスクを残したまま verified に昇格させない）。
  3. 検査を迂回する必要がある正当なケース（タスク分解を伴わない軽量レーンでの修正など）に
     対しては明示的な `--allow-orphan` 等の脱出口を設け、迂回した事実を `STATE.md` に記録する。
     脱出口の要否と語彙は Design Gate で裁定する。
  4. 回帰テストを先行追加する（タスク無しの implementing が拒否されること、未完了タスクを
     残した verified が拒否されること、脱出口指定時のみ通ること、既存の正常系が壊れないこと）。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py`、
  `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`（状態遷移表への事前条件の追記）、
  `tests/test_spec_update.py`、bitz-sdd の3マニフェスト。
- **確認観点**:
  - タスク未起票の要件が `implementing` に入れないこと
  - 未完了タスクを持つ要件が `verified` に入れないこと
  - 軽量レーンの運用（タスク分解を省く小修正）が破綻しないこと — 脱出口の設計が中心論点
  - `spec_inspect.py` の孤児要件検出との**二重実装にならない**こと
    （判定ロジックの正をどちらに置くかを決め、片方は参照に留める）
  - 既存の `tests/test_spec_update.py` が改変なしで PASS し続けること
- **影響推定・ロールバック**: 遷移が新たに失敗しうるようになるため、既存の運用手順に影響する。
  `.spec/` のデータ移行は不要。**現に孤児状態の要件が既存ワークスペースに存在する場合、
  以後その要件の遷移が止まる**可能性があるため、導入前に全ワークスペースの孤児要件ゼロを
  確認する（2026-07-21 時点では 7 ワークスペースすべて PASS）。
  ロールバックは `spec_update.py` とテストの revert で戻る。
- **依存**: なし。`SI-SDD-022`（--by-human の実効性）とは独立に実施できるが、
  どちらも `spec_update.py` の遷移処理に手を入れるため、同時並行は避けて順に実施する。
- **可否の予備判定（推薦）**: **accept 推薦**。根拠:
  - 既存要件との矛盾: なし。CORE-FR-005（権限マトリクスの強制）を事前条件方向に拡張する
  - ガードレール抵触: なし
  - 影響範囲: `spec_update.py` と運用文書。`spec_inspect.py` とは責務境界の整理が要る
  - 軽量レーン適否: **不可**。遷移の成立条件という契約に触れ、脱出口の設計判断を伴うため
    通常フロー + Design Gate を要する
