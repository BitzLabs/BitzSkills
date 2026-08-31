---
id: ADR-022
title: 規範行候補抽出とID構文検証の分離
status: accepted
relations:
  related:
    - ADR-005
    - ADR-013
---

# ADR-022 規範行候補抽出とID構文検証の分離

## Context

従来の規範行Scannerは、先頭トークンが正しい`statement-id`に一致する行だけをParserへ渡していた。
この規則では`REQ-1:AC-01`、未知prefix、3階層ID、ID欠落などを通常本文として無視し、
`EAI-CORE-ID-001`や必須タグ不足を報告できない。

一方、Markdownの通常チェックボックスやコード例まで規範行候補にすると誤検出が増えるため、
候補抽出と完全な構文検証を分離する必要がある。

## Decision

1. Markdown処理を、除外領域判定、規範行候補Scanner、Core Lexer／Parser／Validatorの3段階に分ける。
2. 候補ScannerはIDの妥当性を要求しない。コードブロックと引用の外側で、先頭空白除去後が`- [`で始まり、
   最初の角括弧が文書IDらしい大文字token、Coreタグ、またはProfile名前空間形式である行を候補とする。
3. GFM checkboxの`- [ ]`と`- [x]`は候補から除外する。
4. 候補行のID形式、prefix、階層、必須タグ、順序はLexer／Parser／Validatorが診断する。
5. `approved` REQに妥当な規範文が0件の場合、`SPEC-REQ-STATEMENT-001`／error／`failed`を返す。
6. 不正ID、ID欠落、3階層ID、通常checkbox、コードブロック、引用ブロックの適合性fixtureを必須とする。

## Consequences

- `EAI-CORE-ID-001`が実際に不正IDへ到達する。
- ID欠落や先頭タグ誤りを通常本文として黙って受理しない。
- 通常のMarkdown checkboxと規範文例は引き続き解析対象外にできる。
- Scannerは文書構造を理解するMarkdown Readerの後段で動作する必要がある。

## Alternatives

1. **正しいIDに一致した行だけを解析する**: 不正ID診断が到達不能になるため採用しない。
2. **すべての`- [`行を解析する**: checkboxやMarkdownリンクを誤検出するため採用しない。
3. **approved文書の0件検査だけ追加する**: 個々の不正理由が失われ、draftで問題を発見できないため採用しない。

## Notes

- 本ADRは2026-08-31のP1残存契約レビュー「不正規範行の検出不能」に対する裁定である。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | 候補抽出と完全なID構文検証を分離 | — |
