---
id: ADR-027
title: Diagnostic結果効果・集約・workspace sourceの確定
status: accepted
relations:
  related:
    - ADR-011
    - ADR-021
---

# ADR-027 Diagnostic結果効果・集約・workspace sourceの確定

## Context

ADR-021はDiagnostic severityと操作statusを分離したが、結果JSONのDiagnosticインスタンスには
その診断が操作へ与える`resultStatus`がなく、条件によって複数statusへ対応するコードを機械的に判別できなかった。
集約順序はverifyとdoctorに重複し、モノレポ結果ではworkspace相対`source.path`だけでは同名pathを一意にできなかった。

## Decision

1. Diagnosticの必須フィールドへ`resultStatus`を追加する。値は`passed`、`passed_with_warnings`、
   `failed`、`blocked`、`error`のいずれかとし、そのDiagnostic単独が操作へ与える効果を表す。
2. info Diagnosticは`passed`、warning Diagnosticは`passed_with_warnings`を原則とする。
   error Diagnosticは原因に応じて`failed`、`blocked`、`error`を使用する。
3. 操作statusは、Diagnosticの`resultStatus`、対象別結果、command結果を
   `error > failed > blocked > passed_with_warnings > passed`の順で集約する。
4. `source.kind: file`へ`workspaceId`を必須追加する。単一workspaceでも実効IDを記録し、
   `path`はそのworkspaceのroot相対とする。連合ルート由来はfederation rootのworkspace IDを使う。
5. `source.kind: environment`と`invocation`はworkspaceを持たない原因を表せるため、`workspaceId`を必須にしない。
6. 集約結果に複数statusが混在しても各Diagnosticと対象別結果を保持し、最悪値だけで原因を隠さない。

## Consequences

- Diagnosticコード表を知らないクライアントも、各診断の操作効果を構造的に読める。
- 全操作とモノレポ集約が同じ優先順位を使用する。
- 同じ相対pathを持つ複数workspaceの診断を一意に特定できる。
- Diagnostic fixtureとJSON例へ`resultStatus`、file sourceへ`workspaceId`を追加する必要がある。

## Alternatives

1. **コード表からstatusを逆引きする**: 条件付きstatusのコードでインスタンスを判別できないため採用しない。
2. **source.pathをrepository root相対にする**: 単一workspace結果との互換性と所有境界を崩すため採用しない。
3. **操作ごとに集約順序を定義する**: 新操作追加時に差異が再発するため採用しない。

## Notes

- 本ADRはADR-021を変更せず、実行時Schemaと集約規則を補完する。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | Diagnostic結果効果、共通集約、workspace sourceを確定 | — |
