---
id: DOC-design-adr-NNNN
title: ADR-NNNN <決定タイトル>
status: proposed             # proposed | accepted | deprecated | superseded
version: 0.1.0
changeImpact: medium
project_type: both
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null          # 置換されたら ADR-... を入れる
decides: []                  # このADRが確定させる要件ID（.spec/requirements/ の FR/NFR/CON と対応）
---

<!--
  MADR 準拠。既存の ADR-template.md と整合させること（片方だけ変えない）。
  不採用案は "Considered Options"、試行錯誤は append-only の "Exploration Log" に残す。
-->

# ADR-NNNN: <決定タイトル>

## Context
<何を、なぜ今決める必要があるか。制約・前提。>

## Decision
<採用した結論。1〜数文で言い切る。>

## Considered Options
<!-- 不採用案を理由付きで残す。不採用案は要件として起票せず、ここが唯一の記録場所。 -->
- **<案A（採用）>** — <採用理由>
- **<案B>** — 不採用理由: <なぜ落としたか>
- **<案C>** — 不採用理由: <...>

## Consequences
- **良い影響**: <...>
- **トレードオフ/負債**: <library なら互換性・API 表面積への影響を必ず書く>

## Exploration Log（append-only）
<!-- 決定に至る試行錯誤。過去エントリは編集しない。 -->
- 2026-07-07 — <試したこと / 分かったこと>
