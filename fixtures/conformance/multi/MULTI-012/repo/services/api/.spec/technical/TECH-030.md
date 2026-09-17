---
id: TECH-030
title: API側の監査実装方針
status: approved
relations:
  refines: [platform::REQ-002:AC-01]
tests:
  - path: tests/test_report.py
    covers: [platform::REQ-002:AC-01]
    command: backend
---

# TECH-030 API側の監査実装方針

## Context

apiでREQ-002を実装する。
