---
id: TECH-002
title: 別の実装方針
status: approved
relations:
  refines: [REQ-001]
tests:
  - path: tests/link/test_auth.py
    covers: [REQ-001:AC-01]
    command: default
---

# TECH-002 別の実装方針

## Context

同じテスト割当てへ別のテストを宣言する。
