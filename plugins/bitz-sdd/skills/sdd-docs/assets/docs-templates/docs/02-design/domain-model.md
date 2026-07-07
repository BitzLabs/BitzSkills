---
id: DOC-design-domain-model
title: Domain Model
status: active
version: 0.1.0
changeImpact: low
project_type: app
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null
---

<!-- ドメインの中核概念と関係。glossary は用語定義、ここは構造とルール。 -->

# Domain Model

## 中核エンティティと関係
```
<エンティティ関係図（mermaid/ASCII）>
```

## 不変条件 (Invariants)
- <常に成り立つべき規則。検証可能な受入基準は .planning/ へ>

## library 固有
- ドメイン概念を公開型にどう写像するか（型が利用者の語彙になる）。public-api.md と整合。
