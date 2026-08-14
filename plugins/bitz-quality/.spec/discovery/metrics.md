---
id: QLT-DSC-002
title: "bitz-quality レビュー基盤 成功指標"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# 成功指標

数値は初回baseline未計測のため `[proto / 未検証]` とする。

## North Star Metric

**Contract-valid Review Rate**: 必須schema、入力target、追跡規則、Gate整合をすべて満たす統合レビュー数 / 全レビュー数。
事前目標候補は100%。1件でもinvalidならGate入力へ昇格しない。

## Input Metrics

| 指標 | 定義 | 初期閾値候補 |
|---|---|---|
| Perspective Completion | 必須観点の正常/明示失敗結果数 | 100% |
| Cross-platform Decision Parity | 同一fixtureのverdict一致率 | 100% |
| Finding Schema Validity | schema-valid finding数 | 100% |
| Traceability | P0/P1の`tracked_by`実在率 | 100% |
| Replay Safety | 同一review ID再実行時の重複成果物 | 0件 |

## Guardrails

- 未追跡P0/P1を含むPASS: 0件。
- target SHA不一致を有効判定として受理: 0件。
- 個別結果欠落を暗黙成功として扱う: 0件。
- canonical SDD成果物やGit/PRへの無権限write: 0件。
- token/時間上限はbaseline後に決め、未計測値をSLOとして断定しない。
