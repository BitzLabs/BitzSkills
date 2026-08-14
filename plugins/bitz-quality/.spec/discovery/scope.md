---
id: QLT-DSC-004
title: "bitz-quality レビュー基盤 スコープ"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# スコープ

## Must

- 論理Reviewerとplatform adapterの分離。
- perspective/profile registryと発動条件。
- invocation manifest、個別review result、synthesis、finding、gate preconditionのversion付きschema。
- timeout/部分失敗/未知schema/stale targetの安全側判定。
- deterministic validator、重複排除、finding一意ID、P0/P1追跡。
- 現行`sdd-review`のgolden fixtureと読取互換adapter。

## Should

- review profileのプロジェクト上書き。
- レビュー履歴・再レビュー・carried-over finding。
- platform/model別qualificationと再現性測定。

## Could

- コスト/latency最適化、観点推薦、モデルルーティング。

## Won't（初期系列）

- `sdd-review`の即時削除、SDD status更新、PR merge強制、任意MCP/外部SaaSへの必須依存。
