---
id: TECH-002
title: 認証の実装方針
status: approved
relations:
  requires: [TECH-999]
  refines: [REQ-001]
  related: [ADR-001]
implements: [src/auth.py, src/session.py]
tests:
  - path: tests/test_auth.py
    covers: [REQ-001:AC-01]
    command: default
  - path: tests/test_session.py
    covers: [REQ-001:AC-02]
    command: default
x-owners: [team-auth]
---

# TECH-002 認証の実装方針

## Context

規範文を持たない実装方針。

| 項目 | 値 |
|---|---|
| 方式 | token |
