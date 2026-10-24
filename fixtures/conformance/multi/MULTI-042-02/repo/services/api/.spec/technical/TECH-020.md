---
id: TECH-020
title: API側の段階2の具体化
status: approved
relations:
  refines: [platform::TECH-005:C-01]
tests:
  - path: tests/test_tech_020.py
    covers: [api::TECH-020:C-01]
    command: backend
---

# TECH-020 API側の段階2の具体化

## Context

API側の段階2の具体化を定める。

## Constraints

- [TECH-020:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 形式違反を拒否する。
