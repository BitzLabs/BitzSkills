---
id: TECH-100
title: ルートの具体化
status: approved
relations:
  refines: [alpha::TECH-900:C-01]
tests:
  - path: tests/z2.py
    covers: [TECH-100:C-01, alpha::TECH-900:C-01]
    command: a
  - path: tests/z1.py
    covers: [alpha::TECH-900:C-01]
    command: a
---

# TECH-100 ルートの具体化

## Context

ルートの具体化を定める。

## Constraints

- [TECH-100:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 結果を記録する。
