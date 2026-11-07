---
id: TECH-001
title: API側の実装方針
status: approved
relations:
  refines: [web::REQ-001:AC-01]
tests:
  - path: tests/test_login.py
    covers: [web::REQ-001:AC-01]
    command: absent
---

# TECH-001 API側の実装方針

## Context

API側の実装方針を定める。
