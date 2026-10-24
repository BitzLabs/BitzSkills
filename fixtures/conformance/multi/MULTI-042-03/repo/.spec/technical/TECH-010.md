---
id: TECH-010
title: 別の具体化
status: approved
relations:
  refines: [REQ-001:AC-01]
tests:
  - path: tests/test_tech_010.py
    covers: [TECH-010:C-01]
    command: frontend
---

# TECH-010 別の具体化

## Context

別の具体化を定める。

## Constraints

- [TECH-010:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 応答形式を固定する。
