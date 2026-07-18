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

`plugin-structure` を入口に7つの専門スキル、`create-plugin` コマンド、`agent-creator`・`plugin-validator` エージェントで構成する。スキル作成の方法論は skill-creator へ委譲する。

この文書は Design Gate 前の proposed ドラフトである。詳細設計は `.spec/design/` に作成し、人間レビュー後に active 化する。
