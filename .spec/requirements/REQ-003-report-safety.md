---
id: REQ-003
title: 明示reportの保存先をsymlinkへ逸らさない
status: approved
implements:
  - plugins/bitz-core/src/bitz/reportio.py
tests:
  - path: tests/bitz-core/test_reportio.py
    covers: [REQ-003:AC-01, REQ-003:AC-02, REQ-003:AC-03]
verify: default
---
# REQ-003 明示reportの保存先をsymlinkへ逸らさない

## Intent

`--report`の保存で、report directoryの検査から書込みまでの間に`.spec`または`.spec/reports`がsymlinkへ
差し替えられても、symlink先へ一時fileもreportも作らないようにする。正本は
[結果・Diagnostic・終了コード §8](../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)であり、
本REQは「symlink先のdirectoryへ一時fileもreportも作らない」を、検査と書込みの競合がある場合にも守ることを句にする。

## Acceptance Criteria

- [REQ-003:AC-01] [ACTOR:BitzCore] [WHEN] 明示`--report`でreportを保存する場合 [MUST] [THEN] workspace rootから`.spec`と`.spec/reports`をsymlinkを辿らずに開き、開いたdirectoryの中だけに一時fileとreportを作成する。
- [REQ-003:AC-02] [ACTOR:BitzCore] [IF_ERROR] reportの保存中に`.spec`または`.spec/reports`がsymlinkまたはdirectory以外へ差し替えられた場合 [MUST] [THEN] 差し替え先へ書き込まず`SPEC-REPORT-WRITE-001`を返す。
- [REQ-003:AC-03] [ACTOR:BitzCore] [ALWAYS] [MUST] [CONSTRAINT] reportの保存を終えた時点で、成功と失敗のどちらでもreport directoryに一時fileを残さない。

## Verification

`tests/bitz-core/test_reportio.py`で確認する。差し替えの競合は、検査の直後に`.spec/reports`をsymlinkへ置き換える
試験用の割込みで再現し、symlink先に何も作られないことを確かめる。既存の適合fixture（`SINGLE-071`、`125-05`、
`125-06`）は競合のない保存と失敗を検査しており、引き続き通過する必要がある。
