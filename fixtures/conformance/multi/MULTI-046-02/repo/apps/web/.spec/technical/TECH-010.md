---
id: TECH-010
title: 規範文を直接refinesする具体化
status: approved
relations:
  refines: [web::REQ-001:AC-01]
tests:
  - path: tests/test_tech_010.py
    covers: [web::REQ-001:AC-01, web::TECH-010:C-01]
    command: frontend
---

# TECH-010 規範文を直接refinesする具体化

## Context

規範文を直接refinesする具体化を定める。

## Constraints

- [TECH-010:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 検証を呼び出す。
