---
id: TECH-003
title: 間接の具体化
status: approved
relations:
  refines: [TECH-002:AC-01]
tests:
  - path: tests/test_indirect.py
    covers: [TECH-003:AC-01]
    command: default
---

# TECH-003 間接の具体化

## Context

具体化する技術契約。

## Contract

- [TECH-003:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 形式違反を拒否する。
