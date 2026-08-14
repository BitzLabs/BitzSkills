---
id: QLT-DSN-000
title: "レビュー基盤 設計作業台帳"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# 設計作業台帳

## API導出表

| API | 層 | 由来 |
|---|---|---|
| review plan/run/validate/synthesize | Process | QLT-FR-017〜023 |
| adapter qualification | System | QLT-FR-024 |
| legacy import/shadow compare | Process | QLT-FR-025 |
| summary/result | Experience | QLT-FR-021/023 |
| run history/measurement plan | System | QLT-FR-026 |

## 仮説トレーサビリティ

| 仮説 | 要件 | 設計・検証先 |
|---|---|---|
| H-Q1 | QLT-FR-017/019/024 | adapter port、qualification fixture |
| H-Q2 | QLT-FR-020/021/023 | schema catalog、陽性対照validator test |
| H-Q3 | QLT-FR-018/026 | profile比較、事前固定measurement plan |
| H-Q4 | QLT-FR-017/018/024 | core/adapter分離contract test |
| H-Q5 | QLT-FR-025 | golden corpus、shadow compare |
| H-Q6 | QLT-FR-021/022/025 | consumer境界、権限外write/stale canary |

## Open Questions

- profile overrideの物理配置と所有者。
- adapterの実プロセス起動契約と秘密値境界。
- 初回qualificationのtrial数、token・時間budget。
