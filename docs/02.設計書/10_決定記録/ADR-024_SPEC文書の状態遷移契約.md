---
id: ADR-024
title: 仕様文書の状態遷移契約
status: accepted
relations:
  related:
    - ADR-012
    - ADR-015
---

# ADR-024 仕様文書の状態遷移契約

## Context

REQとTECHの状態の語彙は`draft`、`approved`、`outdated`に限定されていたが、上位の設計の遷移図は
`outdated -> draft`だけを示し、詳細仕様は見直しの後の`outdated -> approved`も許可していた。
ADRとTASKも状態の値の列挙だけで、許可される遷移と終端の状態が確定していなかった。

状態遷移をアダプターや自然言語のスキルへ委ねると、同じ変更が実装の経路によって合格または不合格になる。
一方、人間が意味を確認した事実そのものを、Coreが推測することもできない。

## Decision

1. REQとTECHは、作成するときに`draft`または`approved`を選択できる。
2. REQとTECHの遷移は、`draft -> approved`、`approved -> draft|outdated`、
   `outdated -> draft|approved`と、同じ状態の維持だけを許可する。`draft -> outdated`は禁止する。
3. `approved`と`outdated -> approved`は、人間が意味を確認したという明示的な宣言として扱う。
   Coreは確認した主体を推測せず、必要な`Revision History`と遷移の形だけを検査する。
4. ADRは作成するときに`proposed`、`accepted`、`rejected`を選択できる。既存のADRは
   `proposed -> accepted|rejected`、`accepted -> superseded`と、同じ状態の維持だけを許可し、
   `rejected`と`superseded`を終端とする。
5. TASKは作成するときに`open`だけを許可し、`open -> done`と同じ状態の維持だけを許可する。
   完了の後に追加の作業が必要な場合は、新しいTASKを作り、`done -> open`で再利用しない。
6. Gitの基準版を利用できる`bitz check`は遷移を検査し、禁止された遷移を
   診断`SPEC-STATE-TRANSITION-001`（重大度`error`、結果への効果`failed`）とする。
   基準版を利用できない場合は、現在の値の語彙だけを検査する。
7. Coreは、影響候補を自動的に`outdated`へ変更しない。状態の変更は、人間が確認できる差分として行う。

## Consequences

- 状態の値だけでなく、変更の前後での合法性を、fixtureにできる。
- 承認済み要求の保護と`Revision History`の検査を、同じ遷移の契約へ接続できる。
- `outdated`を再承認するためだけの、不要な`draft`の中間のコミットを要求しない。
- 状態`done`のTASKと状態`rejected`のADRを、別の意味で再利用できない。

## Alternatives

1. **状態の値だけを検査する**: 禁止された遷移の判断をアダプターごとに行う状態が残るため採用しない。
2. **`outdated -> draft -> approved`を必須にする**: 見直しの結果、本文の変更が不要な場合にも、中間のコミットを要求するため採用しない。
3. **Coreが影響候補を自動的に`outdated`へ変更する**: 誤検知で規範文書を適用できない状態にするため採用しない。

## Notes

- 本ADRは2026-08-31のP2の残存契約レビュー「状態遷移の不一致」に対する裁定である。
- TASKの`open -> done`を開発フローの終端へ配置する手順と、状態`done`のTASKを目的ごとに起点にできるかどうかは、
  [ADR-034](ADR-034_TASK完了終端とdone起点操作の確定.md)で補完する。`Decision`の5番目の項目の許可される遷移は変更しない。
- `Decision`の1、2、5番目の項目は、[ADR-036](ADR-036_flow取止めと不採用履歴の保持.md)により部分改訂された。
  REQとTECHへ`rejected`、TASKへ`cancelled`を追加する。`Decision`の3、4、6、7番目の項目は変更しない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | SPEC文書種別ごとの許可状態遷移を確定 | — |
| 2026-09-01 | TASK完了終端と`done`起点操作の補完先を追記 | `ADR-034` |
| 2026-09-01 | Decision 1・2・5を不採用・中止終端の追加により部分改訂 | `ADR-036` |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
