---
id: TECH-002
title: 直接の具体化
status: approved
relations:
  refines: [REQ-001:AC-01]
tests:
  - path: tests/test_direct.py
    covers: [TECH-002:AC-01]
    command: default
---

# TECH-002 直接の具体化

## Context

具体化する技術契約。

## Contract

- [TECH-002:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 入力形式を固定する。
