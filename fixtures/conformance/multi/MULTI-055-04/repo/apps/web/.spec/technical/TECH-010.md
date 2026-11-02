---
id: TECH-010
title: Webの実装方針
status: approved
relations:
  refines: [platform::REQ-001]
tests:
  - path: tests/t.py
    covers: [TECH-010:C-01]
    command: t
---

# TECH-010 Webの実装方針

## Context

実装方針を定める。

## Constraints

- [TECH-010:C-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 画面に利用者のIDを表示しない。
