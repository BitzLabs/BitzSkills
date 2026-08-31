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

Diagnosticの共通契約は`severity`と`source`を必須としていたが、Context、doctor、モノレポの
Diagnostic一覧には操作結果だけを記載した行があり、severityを決定できなかった。またCore版不一致、
Git不在、Capability不足などはファイル位置を持たず、従来の`source.path`例では表現できなかった。

severityと操作statusを同一視すると、前提不足を表す`blocked`やツール障害を表す`error`を、
成果物不適合の`failed`へ誤って集約する実装が生じる。

## Decision

1. Diagnostic severityは`info`、`warning`、`error`の3値とする。
2. 操作statusは`passed`、`passed_with_warnings`、`failed`、`blocked`、`error`の5値とし、
   severityとは別軸とする。
3. 各Diagnostic定義は、条件、severity、その条件が操作へ与えるresult statusを定義する。
4. `info`はstatusを変更せず、`warning`だけが存在する操作は`passed_with_warnings`とする。
   `error` severityは原因に応じて`failed`、`blocked`、`error`のいずれかへ対応できる。
5. `source`は`kind`で判別する`file`、`environment`、`invocation`の3形式とする。
   ファイル由来はworkspace相対pathと任意の行・列・キー、環境由来はcomponentと任意のidentifier、
   呼出し由来は任意のargumentを保持する。
6. EARS-AI Validatorでは、EAI error Diagnosticを成果物不適合の`failed`へ対応付ける。
   この固有規則を全操作へ一般化しない。

## Consequences

- 全Diagnosticを必須フィールド欠落なしでJSON化できる。
- 同じ`error` severityでも、成果物不適合、前提不足、ツール障害を終了コードで区別できる。
- Diagnosticの表示優先度と、呼出し側が分岐する操作statusを独立して利用できる。
- 既存Diagnostic例の`source`へ`kind`を追加する必要がある。
- Context、doctor、モノレポ、SPEC検証の一覧へseverityとresult statusの列が必要になる。

## Alternatives

1. **`source`を任意にする**: 環境診断は表現できるが、診断の発生源を機械判定できなくなるため採用しない。
2. **severityからstatusを一意に導出する**: `blocked`と`error`を正しく区別できないため採用しない。
3. **環境診断だけ別Schemaにする**: アダプターが複数の診断型を扱うことになり、共通契約を失うため採用しない。

## Notes

- 本ADRは2026-08-31のP1残存契約レビュー「Diagnostic共通契約の不足」に対する裁定である。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | severity、操作status、sourceの分離を決定 | — |
