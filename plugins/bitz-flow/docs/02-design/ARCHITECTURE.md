---
id: DOC-design-architecture
title: "Architecture"
status: proposed
version: 0.1.0
changeImpact: low
project_type: library
updated: 2026-07-18
owner: hide
superseded_by: null
---

# Architecture

`flow-core` が状況判定と共通規律、`flow-worktree` が並列分離、`flow-pr` が Issue 駆動 PR を担当する。各スキルは SDD に依存せず自己完結する。

この文書は Design Gate 前の proposed ドラフトである。詳細設計は `.spec/design/` に作成し、人間レビュー後に active 化する。
