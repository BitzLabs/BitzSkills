---
id: TECH-010
title: Web側の実装方針
status: approved
relations:
  requires: [api::TECH-020]
  refines: [platform::REQ-001:AC-01]
tests:
  - path: tests/auth/test_login.py
    covers: [platform::REQ-001:AC-01]
    command: frontend
---

# TECH-010 Web側の実装方針

## Context

webでREQ-001を実装する。
