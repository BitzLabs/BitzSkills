---
id: DOC-implementation-patterns
title: Implementation Patterns
status: active
version: 0.1.0
changeImpact: low
project_type: app            # app | library
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null
---

<!--
  恒久的な実装規約。フィーチャを越えて残る「どう作るか」の標準を持つ。
  ドリフト境界: フィーチャ単位の実装タスク・依存グラフは .planning/（tasks/）。
                ここに書くのは feature を越えて再利用される規約・パターンのみ。
  この層で分割が必要になったら: error-handling.md / dependency-policy.md を兄弟に足す。
-->

# Implementation Patterns

## 採用パターン

- **<パターン名>** — 使う状況: <...>。理由: <...>。反例（使わない状況）: <...>

## 命名・構造の規約

<!-- glossary.md の用語をコード識別子へ一貫反映する（1概念1用語）。 -->
- <規約>

## エラー処理方針（切り出す前はここ）

- **境界での扱い**: <library: 例外を投げるか Result を返すか。公開面で一貫させる>
  - C#: 例外 vs `try`パターン / カスタム例外階層 / `Exception` を握り潰さない
  - TS: `throw` vs `Result`/判別可能 union / 型付きエラー
  - Rust: `Result<T, E>` / `thiserror`・`anyhow` の使い分け / `panic!` は契約違反時のみ

## 依存方針（切り出す前はここ）

<!-- library は依存を最小化（利用者のツリーに載る）。app は運用可能性で選ぶ。 -->
- 依存追加の基準: <...>
- 禁止・要注意の依存: <...>
