---
id: TASK-001
title: 明示reportの保存をdirectory fd基準の操作へ改める
status: done
relations:
  addresses:
    - REQ-003:AC-01
    - REQ-003:AC-02
    - REQ-003:AC-03
changes:
  - plugins/bitz-core/src/bitz/reportio.py
  - tests/bitz-core/test_reportio.py
---
# TASK-001 明示reportの保存をdirectory fd基準の操作へ改める

## Objective

`reportio.write_report`は`.spec`と`.spec/reports`を`lstat`で検査した後、pathの文字列で一時fileを開き、
hard linkで確定している。検査と書込みの間に`.spec/reports`がsymlinkへ差し替えられると、symlink先へ書き込む。
`.spec`と`.spec/reports`をsymlinkを辿らないdirectory fdとして開き、一時fileの作成、確定、除去をそのfd基準で
行うよう改める。

## Completion Criteria

- REQ-003の3句を`tests/bitz-core/test_reportio.py`で確認し、競合の再現試験を含める
- 既存の適合fixture（`uv run fixtures/run_conformance.py --core plugins/bitz-core --step 5`）が全件通過する
- `bitz check TASK-001`が`changes`の範囲外の変更を検出しない
