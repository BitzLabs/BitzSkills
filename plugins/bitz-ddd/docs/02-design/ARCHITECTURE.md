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

3つの独立スキル `ddd-story`、`ddd-model`、`ddd-evaluate` が、BitzSDD の `.spec/design/` 契約へ成果物を出力する。スキル間は相対ファイル参照せず、スキル名によって連携する。

この文書は Design Gate 前の proposed ドラフトである。詳細設計は `.spec/design/` に作成し、人間レビュー後に active 化する。
