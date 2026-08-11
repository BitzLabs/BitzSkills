---
implements: FLW-NFR-011, FLW-FR-013
depends_on: [FLW-TSK-032]
boundary: evals/flow-core/m1-eval/raw_log_guard.py, tests/test_flow_m1_raw_log_guard.py
status: done
---

### raw log guard（owner-only境界・redaction・canary・保持期限・削除証跡）

- **作業内容**: qualification の raw event log を安全に扱う guard を
  `evals/flow-core/m1-eval/raw_log_guard.py` として実装する。

  - **owner-only 境界**で保存する（owner と `evaluation-reviewer` だけが読める permission）。
    未許可 role からの読み取り要求は拒否し、Gate を停止できる判定を返す。
  - repo 外の秘密値を **redaction** する。redaction は `flowlib/sanitize.py` を使い、
    ここで遮断ロジックを再実装しない。redaction version を記録する。
  - **秘密値 canary** を仕込み、書き出した log から**検出できること**を確認する。
    canary が検出できない場合は「redaction が効きすぎて観測不能」または「log が欠落」であり、
    どちらも Gate 停止事由とする（未検出 = 安全ではない）。
  - **保持期限（最大 30 日）**と削除期限・削除担当を記録し、期限超過を検出する。
    削除を実行したら**削除証跡**（対象 digest、実行時刻、担当）を残す。
    証跡の無い削除と、期限超過のまま残っている log はいずれも Gate 停止事由とする。
  - raw log の **digest** を manifest へ渡せる形で公開する。

- **完了条件**: 上記の単体テストが PASS し、次の負の対照が拒否されること —
  group / other から読める permission での保存、redaction を通さない生 log の保存、
  canary 未検出、保持期限 30 日を超える設定、削除証跡なしの削除、期限超過 log の放置。
  秘密値を含む log で redaction 後に秘密値が残らないこと（検出率 100%）。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: 遮断そのものの実装は sanitizer が正であり、本タスクは**保存境界とライフサイクル**を担当する。
  legal hold は別 record がある場合のみ 30 日を超えられるが、その判断は人間が行う（自動延長しない）。
