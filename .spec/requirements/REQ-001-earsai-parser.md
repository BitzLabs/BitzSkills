---
id: REQ-001
title: EARS-AI規範文の解析
status: draft
implements:
  - plugins/bitz-core/src/bitz/earsai/scanner.py
  - plugins/bitz-core/src/bitz/earsai/lexer.py
  - plugins/bitz-core/src/bitz/earsai/parser.py
  - plugins/bitz-core/src/bitz/earsai/ir.py
tests:
  - path: tests/bitz-core/test_earsai_parser.py
    covers: [REQ-001:AC-01, REQ-001:AC-02, REQ-001:AC-03]
  - path: tests/bitz-core/test_earsai_scanner.py
    covers: [REQ-001:AC-04]
verify: default
---
# REQ-001 EARS-AI規範文の解析

## Intent

SPEC文書の規範文を、全操作が同じ構造として扱えるSemantic IRへ決定論的に変換する。
正本は[EARS-AI言語・Semantic IR仕様](../../docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md)であり、
本REQはbitz-core自身の実装が守る観測可能な結果だけを句にする。

## Acceptance Criteria

- [REQ-001:AC-01] [ACTOR:BitzCore] [WHEN] 構文が妥当な規範行候補を解析した場合 [MUST] [THEN] EARS-AI仕様 §6の全fieldを持つSemantic IRを候補ごとに1件返す。
- [REQ-001:AC-02] [ACTOR:BitzCore] [IF_ERROR] 1つの候補行で同じraw原因から複数の構文条件が成立した場合 [MUST] [THEN] Diagnostic registryのpriorityが最小の条件だけを返す。
- [REQ-001:AC-03] [ACTOR:BitzCore] [ALWAYS] [MUST] [CONSTRAINT] 同一入力と同一versionから同一のSemantic IRと構文条件を返す。
- [REQ-001:AC-04] [ACTOR:BitzCore] [WHEN] fenced code block、引用、4 SP以上のindent、task listの行を走査する場合 [MUST] [THEN] その行を規範行候補にしない。

## Verification

`tests/bitz-core/`の単体試験で各句を確認する。適合fixtureのうち`parserChecks`を持つ4件は
`tests/bitz-core/parser_adapter.py`が全Semantic IRを完全比較し、Gate B Step 2で受け入れた。
