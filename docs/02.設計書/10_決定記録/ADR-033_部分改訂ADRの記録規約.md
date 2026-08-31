---
id: ADR-033
title: 部分改訂ADRの記録規約
status: accepted
relations:
  related:
    - ADR-020
---

# ADR-033 部分改訂ADRの記録規約

## Context

決定記録READMEは「決定を変更する場合は既存ADRのDecisionを書き換えず、後継ADRを作成して後継側の
`relations.supersedes`に旧IDを書き、旧ADRの`status`を`superseded`にする」と定めている。この規則は
ADR全体が置き換わる場合を想定しており、Decision項目の一部だけが置き換わる場合を区別していない。

一方、[ADR-020](ADR-020_決定記録をSPEC本文構造規定へ適合させる.md) Decision 4は`Amends`相当の型付き語彙が
Coreにないため`related`で表すとし、改訂関係の機械追跡は実測で必要になった時点で裁定するとした。
`related`は閲覧用の弱い関係であり、どのDecision項目が後続ADRで変更されたかを示さない。

現在、`accepted`のまま部分改訂されたADRが5件ある。

| 旧ADR | 部分改訂した後継 |
|---|---|
| ADR-005 | ADR-013 |
| ADR-009 | ADR-010, ADR-011, ADR-016 |
| ADR-010 | ADR-012, ADR-014, ADR-015 |
| ADR-014 | ADR-015 |
| ADR-018 | ADR-030 |

ADR-026はADR-030から参照されるが、Decision項目は置き換わっておらず、正本の所在を示す明確化である。

いずれも旧ADRの`Revision History`が後継IDをReference列に持つ。欠けているのは、どのDecision項目が
置き換わったかの明示である。`accepted` ADRだけを読んだ実装者は、後発順序を知らなければ衝突を
解消できない。

## Decision

1. ADRの部分改訂を許可する。後続ADRが旧ADRのDecision項目の一部だけを置き換える場合、旧ADRは
   `accepted`のままとし、`supersedes`／`superseded`を使わない。
2. 全Decision項目が置き換わる場合だけ、後継ADRの`relations.supersedes`と旧ADRの
   `status: superseded`を使う。READMEの現行規則はこの2分岐へ書き分ける。
3. 部分改訂は次の3点をすべて記録する。

   1. **後継ADR**: Decision本文に、置き換える旧ADR IDとDecision項目、および他のDecisionを変更しない
      ことを明記する。`relations.related`へ旧ADRを含める。
   2. **旧ADR**: `Notes`へ、どのDecision項目がどの後継ADRへ移ったかを記載する。
   3. **旧ADR**: `Revision History`へ1行追加し、Summaryへ対象Decision項目、Reference列へ後継ADR IDを
      書く。

4. Decisionが番号付き箇条書きでないADRでは、Decision項目の代わりに該当箇所を一意に特定できる語句を
   用いる。番号を後付けするためにDecision本文を書き換えない。
5. `x-amends`などのFrontmatter拡張キーと、`amends`相当の新しい関係型を追加しない。ADR-020 Decision 4の
   後段（改訂関係の機械追跡が実測で必要になった場合に新しい関係型を裁定する）は維持する。
6. 既存5件を本規約へ移行する。ADR-018はADR-030の裁定時に適合済みであり、ADR-005、ADR-009、ADR-010、
   ADR-014へ`Notes`と`Revision History`を補う。Decision項目を置き換えない明確化は部分改訂に当たらず、
   3点記録を要求しない（ADR-026がこれに当たる）。
7. 本決定はADR-020 Decision 4のうち、`Amends`相当を`related`だけで表すとした部分を置き換える。
   ADR-020の他のDecisionは変更しない。

## Consequences

- `accepted` ADR間の優先関係が、旧ADR単体を読んだだけで追跡できる。
- 部分改訂の記録が3箇所に分散するが、いずれも既存のH2構成の中に収まり、新しい書式を導入しない。
- 検証器を持たないFrontmatterキーが増えないため、書式だけが残って実態と乖離する状態を避けられる。
- 部分改訂の記録漏れは機械検出されず、レビューで担保する。
- 本ADR自身がADR-020の部分改訂であり、規約の最初の適用事例となる。

## Alternatives

1. **`x-amends`と改訂対象Decision番号をFrontmatterへ追加する**: 本ディレクトリは`docs/`配下の設計資料で
   あり、Coreは走査しない（ADR-020 Decision 5）。読む主体のないスキーマは書式だけが残る。ADR-020
   Decision 4が新しい関係型の追加条件を「機械追跡が実測で必要になった場合」としており、その条件を
   まだ満たさないため採用しない。
2. **部分改訂を禁止し、統合後継ADRへ集約する**: ADR-009とADR-010は現行決定の大半が有効なまま設計書
   本文から多数参照されており、`superseded`にすることは事実に反する。ADRを追記型の記録とする前提とも
   矛盾するため採用しない。
3. **現状のまま`related`と`Revision History`に委ねる**: どのDecision項目が置き換わったかを示せず、
   指摘された問題が解消しないため採用しない。

## Notes

- 本ADRは2026-08-31のユースケース・フロー遷移レビューUC-FLOW-008に対する裁定である。
- 関連文書: [決定記録README](README.md), [ADR-020](ADR-020_決定記録をSPEC本文構造規定へ適合させる.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | ADR部分改訂の許可と3点記録規約を確定 | — |
