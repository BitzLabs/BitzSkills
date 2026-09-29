---
id: ADR-021
title: Diagnostic severity・操作status・source Schemaの分離
status: accepted
relations:
  related:
    - ADR-011
    - ADR-018
    - ADR-019
---

# ADR-021 Diagnostic severity・操作status・source Schemaの分離

## Context

診断の共通契約は`severity`と`source`を必須としていたが、`context`、`doctor`、複合ワークスペースの
診断の一覧には、操作の結果だけを記載した行があり、重大度を決定できなかった。またCoreのバージョンの不一致、
Git不在、対応機能の不足などはファイルの位置を持たず、従来の`source.path`の例では表現できなかった。

重大度と操作の結果の状態を同一視すると、前提の不足を表す`blocked`やツールの障害を表す`error`を、
成果物の不適合を表す`failed`へ誤って集約する実装が生じる。

## Decision

1. 診断の重大度は`info`、`warning`、`error`の3つの値とする。
2. 操作の結果の状態は`passed`、`passed_with_warnings`、`failed`、`blocked`、`error`の5つの値とし、
   重大度とは別の軸とする。
3. 各診断の定義は、条件、重大度、その条件が操作へ与える結果への効果を定義する。
4. 重大度`info`は結果の状態を変更せず、重大度が`warning`の診断だけがある操作は`passed_with_warnings`とする。
   重大度`error`は、原因に応じて`failed`、`blocked`、`error`のいずれかへ対応できる。
5. `source`は、`kind`で判別する`file`、`environment`、`invocation`の3つの形式とする。
   `file`由来はワークスペース相対のパスと任意の行、列、キーを、`environment`由来は`component`と任意の`identifier`を、
   `invocation`由来は任意の`argument`を保持する。
6. EARS-AIの検証プログラムでは、`EAI`の診断のうち重大度`error`のものを、成果物の不適合を表す`failed`へ対応付ける。
   この固有の規則を全操作へ一般化しない。

## Consequences

- すべての診断を、必須フィールドの欠落なしでJSONにできる。
- 同じ重大度`error`でも、成果物の不適合、前提の不足、ツールの障害を、終了コードで区別できる。
- 診断の表示上の優先度と、呼出し側が分岐に使う操作の結果の状態を、独立して利用できる。
- 既存の診断の例の`source`へ、`kind`を追加する必要がある。
- `context`、`doctor`、複合ワークスペース、仕様文書の検証の一覧へ、重大度と結果への効果の列が必要になる。

## Alternatives

1. **`source`を任意にする**: 環境に由来する診断は表現できるが、診断の発生元を機械で判定できなくなるため採用しない。
2. **重大度から結果の状態を一意に導出する**: `blocked`と`error`を正しく区別できないため採用しない。
3. **環境に由来する診断だけを別のスキーマにする**: アダプターが複数の診断の型を扱うことになり、共通契約を失うため採用しない。

## Notes

- 本ADRは2026-08-31のP1の残存契約レビュー「Diagnostic共通契約の不足」に対する裁定である。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | severity、操作status、sourceの分離を決定 | — |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
