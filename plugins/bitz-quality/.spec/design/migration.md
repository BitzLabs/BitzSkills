---
id: QLT-DSN-004
title: "sdd-review 段階移管計画"
status: active
version: 1.0
updated: 2026-08-14
owner: br7.hide
implements: [QLT-FR-025]
---

# sdd-review 段階移管計画

## 原則

quality側基盤の完成とsdd-reviewの所有権移管を同一Gateで行わない。既存成果物の正とconsumerを保ったまま、
加法導入→shadow→consumer切替→deprecated→削除の順に進む。

## Stages

| Stage | 正 | 出口条件 | rollback |
|---|---|---|---|
| M0 Contract | sdd-review | schema・validator・golden corpusをquality側に追加 | 追加物のみrevert |
| M1 Shadow | sdd-review | 必須field100%、P0/P1消失0、verdict差0、3platform qualification PASS | shadow停止 |
| M2 Consumer opt-in | sdd-review既定 / quality任意 | SDD adapter canary、既存review読取互換、運用観測 | opt-in解除 |
| M3 Default switch | quality-review | V1→Quality→V1往復canary、migration doctor、旧参照一覧 | sdd-review入口へ戻す |
| M4 Deprecation | quality-review | 1 release系列の猶予、旧入口利用0、全consumer移行 | deprecated解除 |
| M5 Removal | quality-review | 人間Promotion Gate、GatePassage、rollback資産確認 | 直前releaseへdowngrade |

## No-Go

- golden corpusでP0/P1、GatePrecondition、carried-over、verdictの意味が1件でも失われる。
- qualityがSDD status/GatePassageを所有しないと移管できない。
- いずれかの必須platformでqualificationを再現できない。
- legacy成果物を破壊的に変換しなければconsumerが成立しない。

## SDD側の後続作業

移管を裁定した段階で、bitz-sdd workspaceへ別spec-issueを委託し、依存manifest、sdd-core routing、
sdd-designのGate接続、sdd-report consumer、migration doctor、version bumpを個別要件化する。
