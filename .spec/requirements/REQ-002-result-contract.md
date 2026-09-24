---
id: REQ-002
title: 操作結果のstatus集約と終了コード
status: draft
implements:
  - plugins/bitz-core/src/bitz/resultmodel.py
tests:
  - path: tests/bitz-core/test_resultmodel.py
    covers: [REQ-002:AC-01, REQ-002:AC-02, REQ-002:AC-03]
verify: default
---
# REQ-002 操作結果のstatus集約と終了コード

## Intent

利用者とSkillが、操作の成否を結果JSONのstatusと終了コードの両方から同じ意味で判定できるようにする。
正本は[結果・Diagnostic・終了コード](../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)である。

## Acceptance Criteria

- [REQ-002:AC-01] [ACTOR:BitzCore] [ALWAYS] [MUST] [CONSTRAINT] 操作結果のstatusをDiagnosticの`resultStatus`のうち最も重いものへ集約する。
- [REQ-002:AC-02] [ACTOR:BitzCore] [WHEN] 操作が結果を返して終了する場合 [MUST] [THEN] `passed`と`passed_with_warnings`は0、`failed`は1、`blocked`は2、`error`は3を終了コードとして返す。
- [REQ-002:AC-03] [ACTOR:BitzCore] [ALWAYS] [MUST] [CONSTRAINT] Diagnosticをsource workspace ID、path、line、column、code、specRefsの辞書順で並べる。

## Verification

`tests/bitz-core/test_resultmodel.py`で集約、終了コード対応、sort順を確認する。
CLI全体での一致は適合fixtureの終了コード比較が担う。
