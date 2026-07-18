---
id: DOC-reference-external-apis
title: 外部APIとリファレンス
status: active
version: 0.1.0
changeImpact: low
project_type: app            # app | library | both
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null
---

<!--
  外部依存の契約・参照と移行ガイドの索引。
  自プロジェクトが「利用する側」の外部 API を記録する（自分が提供する契約は 公開API.md）。
-->

# 外部APIとリファレンス

## 依存する外部 API / サービス

| 名称 | 用途 | バージョン/契約 | 障害時の想定 |
|---|---|---|---|
| <API名> | <...> | <ver / SLA> | <フォールバック> |

## 移行ガイド

破壊的変更 (major) ごとに `migration/<version>.md` を追加する。

- [<version> migration](migration/<version>.md) — <要点>

<!--
  library では利用者向けの移行手順が特に重要。public-api.md の非推奨→削除に対応させる。
  app では外部 API 更新への追随手順をここに集約する。
-->

## 参照資料

- <仕様書・RFC・社内ドキュメントへのリンク>
