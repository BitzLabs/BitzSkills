---
id: ADR-024
title: SPEC文書の状態遷移契約
status: accepted
relations:
  related:
    - ADR-012
    - ADR-015
---

# ADR-024 SPEC文書の状態遷移契約

## Context

REQ／TECHの状態語彙は`draft`、`approved`、`outdated`に限定されていたが、上位設計の遷移図は
`outdated -> draft`だけを示し、詳細仕様は見直し後の`outdated -> approved`も許可していた。
ADRとTASKも状態値の列挙だけで、許可遷移と終端状態が確定していなかった。

状態遷移をアダプターや自然言語スキルへ委ねると、同じ変更が実装経路によって合格または不合格になる。
一方、人間が意味を確認した事実そのものをCoreが推測することもできない。

## Decision

1. REQ／TECHは、作成時に`draft`または`approved`を選択できる。
2. REQ／TECHの遷移は、`draft -> approved`、`approved -> draft|outdated`、
   `outdated -> draft|approved`と同一状態の維持だけを許可する。`draft -> outdated`は禁止する。
3. `approved`と`outdated -> approved`は、人間が意味を確認したという明示的な宣言として扱う。
   Coreは確認主体を推測せず、必要なRevision Historyと遷移形だけを検査する。
4. ADRは作成時に`proposed`、`accepted`、`rejected`を選択できる。既存ADRは
   `proposed -> accepted|rejected`、`accepted -> superseded`と同一状態の維持だけを許可し、
   `rejected`と`superseded`を終端とする。
5. TASKは作成時に`open`だけを許可し、`open -> done`と同一状態の維持だけを許可する。
   完了後に追加作業が必要な場合は新しいTASKを作り、`done -> open`で再利用しない。
6. Git基準版を利用できる`bitz check`は遷移を検査し、禁止遷移を
   `SPEC-STATE-TRANSITION-001`／error／`failed`とする。基準版を利用できない場合は現在値の語彙だけを検査する。
7. Coreは影響候補を自動的に`outdated`へ変更しない。状態変更は人間が確認可能なdiffとして行う。

## Consequences

- 状態値だけでなく、変更前後の合法性をfixture化できる。
- 承認済みREQ保護とRevision Historyの検査を同じ遷移契約へ接続できる。
- `outdated`を再承認するためだけの不要な`draft`中間commitを要求しない。
- 完了TASKと却下ADRを別の意味で再利用できない。

## Alternatives

1. **状態値だけを検査する**: 禁止遷移をアダプターごとに判断する状態が残るため採用しない。
2. **`outdated -> draft -> approved`を必須にする**: 見直しの結果、本文変更が不要な場合にも中間commitを要求するため採用しない。
3. **Coreが影響候補を自動的に`outdated`へ変更する**: 誤検知で規範文書を適用不能にするため採用しない。

## Notes

- 本ADRは2026-08-31のP2残存契約レビュー「状態遷移の不一致」に対する裁定である。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | SPEC文書種別ごとの許可状態遷移を確定 | — |
