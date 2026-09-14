---
id: TECH-001
title: 文書単位testの実装方針
status: approved
implements: [src/auth.py]
tests:
  - path: tests/test_auth.py
    covers: [TECH-001]
    command: default
---

# TECH-001 文書単位testの実装方針

## Context

規範文を持たず文書単位のtestだけを宣言する。
