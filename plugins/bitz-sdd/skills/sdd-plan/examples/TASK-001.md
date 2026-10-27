---
id: TASK-001
title: 空入力の拒否と回帰テストを実装する
status: open
relations:
  addresses:
    - REQ-001:AC-01
changes:
  - src/input.py
  - tests/test_input.py
---

# TASK-001 空入力の拒否と回帰テストを実装する

## Objective

REQ-001:AC-01の意味が人間に承認された後、指定境界内で空入力の拒否を実装する。

## Completion Criteria

実装の前後のCore検査、対象テスト、最終差分の人手レビューを経て完了する。
起点REQがdraftの間は実装へ着手しない。
