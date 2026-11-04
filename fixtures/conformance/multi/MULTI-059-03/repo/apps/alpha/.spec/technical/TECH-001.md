---
id: TECH-001
title: AC-01の実装方針
status: approved
relations:
  refines: [zeta::REQ-001:AC-01]
tests:
  - path: tests/t.py
    covers: [TECH-001:C-01]
    command: t
---

# TECH-001 AC-01の実装方針

## Context

AC-01の実装方針を定める。

## Constraints

- [TECH-001:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 画面に利用者のIDを表示しない。
