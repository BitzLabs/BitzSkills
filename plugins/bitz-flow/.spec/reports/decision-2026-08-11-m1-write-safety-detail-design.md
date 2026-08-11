---
id: FLW-DEC-011
title: "M1 write safety詳細設計の採用"
status: active
version: 1.0
updated: 2026-08-11
owner: user
---

# 裁定記録 — M1 write safety詳細設計の採用

- **裁定者**: user
- **裁定日**: 2026-08-11
- **対象**: FLW-DSN-015、FLW-REV-010
- **裁定**: 提案どおり詳細設計へ反映し、レビューで重大指摘が解消した場合は採用する。

## 根拠

M1 Git writeは重複副作用や誤った成功帰属が起きると復旧が難しいため、M1実装前にレビュー内容を
実装可能な契約へ落とす。FLW-REV-010はconsistency、data-integrity、operations、risk、businessの
全観点で再レビューし、未解消critical/major 0件、判定PASS 4.00となった。

## 採用する境界

- storageが強制できないfencingを主張せず、localはnative lock＋CAS、remoteはserver-side CASとする。
- coordinator coreをROI非依存のM1-1へ置き、M1-2 qualificationを最初のblocking Go/No-Goとする。
- durable intent、quarantine解除、evidence ledger、RPO 0、30 fault fixtureを実装完了条件へ含める。
- 6 PR / 20 sessionを維持し、区分超過またはROI未達は人間へ再提示する。

## 次アクション

FLW-DSN-015をactiveへ遷移し、M1-1から1 task 1 fileでタスク分解する。
