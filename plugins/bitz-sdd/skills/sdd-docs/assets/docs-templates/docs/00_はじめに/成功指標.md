---
id: DOC-context-success-metrics
title: Success Metrics
status: proposed             # Design Gate で人間が active 化する
version: 0.1.0
changeImpact: medium
project_type: app            # app | library
updated: 2026-07-08
owner: <担当ハンドル>
superseded_by: null
---

<!--
  sdd-discovery が生成する proposed ドラフト。
  同一テンプレが sdd-discovery スキルの assets/ にもある（変更時は両方を同期すること）。
  ガードレールの数値は後段で NFR（benchmark/load-test）に派生する — 検証可能な形で書く。
-->

# Success Metrics

## North Star Metric

- **指標**: <顧客に届いた価値を顧客の言葉で>
- **定義**: <測定単位・母集団・期間>
- **測定方法/ソース**: <どこから取るか>
- **目標値**: <値 or TBD（根拠のない数値は書かない）>

## 入力指標（3〜5個）

| 指標 | 定義 | レバー（動かすプロダクトの仕事） | 測定方法 | 目標値 |
|---|---|---|---|---|

## ファネル/フレーム対応（AARRR または HEART のどちらか）

<NSM と入力指標をファネル/次元に配置し、戦略がどの段階に賭けているかを示す>

## ガードレール（NSM 最適化中に劣化させない対抗指標）

| ガードレール指標 | 閾値 | なぜ守るか |
|---|---|---|

## Open Questions

- [ ] <TBD の目標値と、その決め方>
