---
id: TECH-001
title: 認証の実装方針
status: approved
relations:
  refines: [REQ-001]
tests:
  - path: tests/test_tech1.py
    covers: [TECH-001:C-01]
    command: default
---

# TECH-001 認証の実装方針

## Context

実装方針を定める。

## Constraints

- [TECH-001:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を記録しない。
