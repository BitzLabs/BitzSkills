---
id: TECH-001
title: 認証の実装方針
status: approved
relations:
  refines: [REQ-001]
implements: [src/auth.py]
tests:
  - path: tests/test_shared.py
    covers: [REQ-001:AC-01]
    command: default
---

# TECH-001 認証の実装方針

## Context

規範文を持たない実装方針。
