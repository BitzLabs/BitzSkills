---
id: DOC-knowledge-postmortem-YYYYMMDD
title: Postmortem — <一行タイトル>
status: active
version: 1.0.0
changeImpact: low
project_type: app            # app | library
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null
---

<!--
  非難なし (blameless) のポストモーテム。事象ごとに1ファイル。
  恒久的な教訓は LESSONS_LEARNED.md に1行で昇格させ、相互リンクする。
-->

# Postmortem: <一行タイトル>

- **発生日 / 検知**: <...>
- **影響**: <利用者・範囲・期間>
- **重大度**: <...>

## 経緯 (Timeline)
- <時刻> — <出来事>

## 根本原因
<なぜ起きたか。表層でなく構造要因まで>

## 検知と対応
<どう気づき、どう収束させたか>

## 再発防止
- [ ] <アクション>（→ 恒久教訓は LESSONS_LEARNED.md / 契約変更は ADR / 検証は .spec/）

## 学び
<LESSONS_LEARNED.md に昇格する1行の要約>
