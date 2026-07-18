---
id: INF-000
title: "インフラ設計作業台帳"
status: draft
version: 1.0
updated: YYYY-MM-DD
owner:
---

# インフラ設計作業台帳（.spec/design/infra/worksheet.md にコピーして使う）

短命の作業成果物。結論は docs/（運用・リリース.md / セキュリティモデル.md / ADR）の proposed ドラフトへ。

## 実行した領域

- [ ] インフラ構成 / [ ] セキュリティ / [ ] 可観測性・SLO / [ ] 災害復旧 / [ ] コスト

## サービス階層

| サービス/コンテキスト | 階層（critical/standard/best-effort） | 根拠 |
|---|---|---|

## SLO 表

| サービス | SLI（何をどう測る） | SLO（目標・期間） | SLA（対外・バッファ） | エラーバジェット方針 |
|---|---|---|---|---|

## RTO / RPO 表

| サービス | RTO | RPO | 達成手段（バックアップ/フェイルオーバー） | 検証方法 |
|---|---|---|---|---|

## セキュリティ統制表

| 統制 | 対象 | 実現方法 | 検証（sast/dep-audit/manual-check） |
|---|---|---|---|

## 恒久判断（ADR ドラフト行き）

| 判断 | 候補と採否 | 根拠（NFR/制約の引用） |
|---|---|---|

## Open Questions / TBD

- [ ] <根拠待ちの数値・未決の構成>
