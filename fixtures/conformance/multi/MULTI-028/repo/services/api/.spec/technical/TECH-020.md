---
id: TECH-020
title: API側の文書単位の監査方針
status: approved
tests:
  - path: tests/test_audit.py
    covers: [TECH-020]
    command: backend
---

# TECH-020 API側の文書単位の監査方針

## Context

規範文を持たず、文書単位のテストだけを宣言する。
