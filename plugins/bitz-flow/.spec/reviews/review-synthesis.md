---
id: FLW-REV-002
title: "bitz-flow v2 多観点設計レビュー"
status: active
version: 4.0
updated: 2026-07-29
owner: hide
decision: PASS
---

# FLW-REV-002 bitz-flow v2 多観点設計レビュー

- **review_id**: FLW-REV-002
- **対象**: `plugins/bitz-flow/.spec/discovery/*.md`、`design/*.md`、
  `requirements/*.md`、`spec-issues/*.md`
- **判定**: **PASS**
- **集計スコア**: 4.71（PASS ≥ 3.5 / CONDITIONAL ≥ 2.5）
- **適用注記**: 内部DBは持たないが、Git refs/index/worktree、file、GitHubという永続状態を
  変更するためdata-integrityを有効化した。

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 5.00 | 0.15 | v1/v2規範、状態、操作、milestone、指標が整合 |
| data-integrity | 4.35 | 0.25 | recoveryとatomicityは成立。cross-hostとdoctor同期が残余 |
| operations | 5.00 | 0.20 | 監査、復旧、承認境界、timeout、rollbackが実装可能 |
| risk | 4.70 | 0.25 | fail-closedとcanaryで主要リスクを統制 |
| business | 4.65 | 0.15 | 成功指標と出荷境界は整合。用語・timeboxのみ後続裁定 |

findings: 統合前5件 → 重複排除後4件（P0: 0 / P1: 0 / P2: 4 / P3: 0）

## 前回FAILからの解消

1. FLW-DSN-011でv1-current、v2-proposed、v2-approved、v2-currentの適用時点と
   Promotion Gate、rollbackを定義した。
2. Design Gate前はv2設計の`implements`を空にし、PASSした設計からのみ後続EARS要件を派生する
   正しいゲート順序へ修正した。
3. FLW-DSN-012で全公開action、状態写像、承認区分、postcondition、retry、Recovery IDを統合した。
4. FLW-DSN-013で全writeのForward Recovery、PARTIAL/INDETERMINATE、timeout収束、
   atomic file I/O、明示承認の責任境界を定義した。
5. FLW-DSN-014でGitHub capability、固定allowlist adapter、M0 Contract Kernel、
   3platform評価と停止条件を固定した。

## P0 — Blocker

なし。

## P1 — Must Fix

なし。

## P2 — Follow-up

- **SYN-101** [DIN-101, RSK-101] cross-host競合はsingle coordinator運用に依存する。
  M3/M4 canaryでcoordinator identityとmarker重複を検査する。
- **SYN-102** [DIN-301] 自己完結flow-doctorとのschema同期はgolden testに依存する。
  M1のrelease gateへ共通envelope検査を入れる。
- **SYN-103** [BIZ-301] 「200UE」の原意を遅くともM3要件承認前に裁定する。
- **SYN-104** [BIZ-401] M1〜M5の最大PR数／作業session数を要件・タスク分解で定量化する。

## Design Gateへの勧告

技術設計はDesign Gateへ提出可能である。これは実装開始の承認ではない。人間がDesign Gateを
承認した後にだけ、v2 EARS要件をdraft起票し、要件承認を経てM0実装へ進む。

SI-FLW-002〜005は現在openであり、Design Gate承認がissue裁定を兼ねることはない。
各issueをaccept/rejectし、reject時は提案固有要素を除去するか、独立したDiscovery／review根拠へ
由来を付け替えてから設計をactive化する。
