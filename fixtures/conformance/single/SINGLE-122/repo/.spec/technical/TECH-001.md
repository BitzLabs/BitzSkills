---
id: TECH-001
title: 認証の実装方針
status: approved
relations:
  refines: [REQ-001]
  related: [ADR-001]
verify: default
implements: [src/auth.py]
tests:
  - path: tests/test_auth.py
    covers: [REQ-001:AC-02]
    command: other
  - path: tests/test_auth.py
    covers: [REQ-001:AC-01, REQ-001:AC-02]
    command: default
  - path: tests/test_auth.py
    covers: [REQ-001:AC-01]
  - path: tests/test_auth.py
    covers: [REQ-001:AC-01]
    command: default
---

# TECH-001 認証の実装方針

## Context

規範文を持たない実装方針。

| 項目 | 値 |
|---|---|
| 方式 | token |
