---
id: TECH-005
title: 起点側の具体化
status: approved
relations:
  refines: [REQ-001:AC-01]
tests:
  - path: tests/test_tech_005.py
    covers: [platform::TECH-005:C-01]
    command: platform
---

# TECH-005 起点側の具体化

## Context

起点側の具体化を定める。

## Constraints

- [TECH-005:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 入力を検証する。
