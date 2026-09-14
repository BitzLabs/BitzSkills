---
id: TECH-002
title: sessionの実装方針
status: approved
relations:
  refines: [REQ-002]
implements: [src/session.py]
tests:
  - path: tests/test_shared.py
    covers: [REQ-002:AC-01]
    command: default
---

# TECH-002 sessionの実装方針

## Context

規範文を持たない実装方針。
