---
id: TECH-001
title: 規範文を持つ技術契約
status: approved
relations:
  requires: [TECH-009]
tests:
  - path: tests/test_contract.py
    covers: [TECH-001:AC-01, TECH-001:AC-02]
    command: default
---

# TECH-001 規範文を持つ技術契約

## Context

具体化する技術契約。

## Contract

- [TECH-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 応答形式を固定する。
- [TECH-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 応答時間を記録する。
