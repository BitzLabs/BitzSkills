---
id: TECH-002
title: 記録の実装方針
status: approved
relations:
  refines: [TECH-001]
tests:
  - path: tests/test_tech2.py
    covers: [TECH-002:C-01]
    command: default
---

# TECH-002 記録の実装方針

## Context

実装方針を定める。

## Constraints

- [TECH-002:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 記録に利用者の識別子を含めない。
