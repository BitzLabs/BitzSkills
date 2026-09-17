---
id: TECH-020
title: API側の監査方針
status: approved
tests:
  - path: tests/test_audit.py
    covers: [api::TECH-020:AC-01]
    command: backend
---

# TECH-020 API側の監査方針

## Context

監査logの方針を定める。

## Acceptance Criteria

- [TECH-020:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 監査logを残す。
- [TECH-020:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 監査logを保持する。
