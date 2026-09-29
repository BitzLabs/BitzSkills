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

ADR-021は診断の重大度と操作の結果の状態を分離したが、結果のJSONに含まれる個々の診断には、
その診断が操作へ与える`resultStatus`がなく、条件によって複数の結果の状態に対応する診断コードを機械的に判別できなかった。
集約の順序は`verify`と`doctor`に重複し、複合ワークスペースの結果では、ワークスペース相対の`source.path`だけでは
同名のパスを一意にできなかった。

## Decision

1. 診断の必須フィールドへ`resultStatus`を追加する。値は`passed`、`passed_with_warnings`、
   `failed`、`blocked`、`error`のいずれかとし、その診断が単独で操作へ与える効果を表す。
2. 重大度`info`の診断は`passed`、重大度`warning`の診断は`passed_with_warnings`を原則とする。
   重大度`error`の診断は、原因に応じて`failed`、`blocked`、`error`を使用する。
3. 操作の結果の状態は、診断の`resultStatus`、対象別の結果、コマンドの結果を
   `error > failed > blocked > passed_with_warnings > passed`の順で集約する。
4. `source.kind: file`へ`workspaceId`を必須のフィールドとして追加する。単一ワークスペースでも実効IDを記録し、
   `path`はそのワークスペースのルート相対とする。複合ワークスペースのルート由来は、ルートワークスペースの
   ワークスペースIDを使う。
5. `source.kind: environment`と`invocation`は、ワークスペースを持たない原因を表せるため、`workspaceId`を必須にしない。
6. 集約した結果に複数の結果の状態が混在しても、個々の診断と対象別の結果を保持し、最悪値だけで原因を隠さない。

## Consequences

- 診断コードの表を知らないクライアントも、各診断が操作へ与える効果を構造的に読める。
- すべての操作と複合ワークスペースの集約が、同じ優先順位を使用する。
- 同じ相対パスを持つ複数のワークスペースの診断を、一意に特定できる。
- 診断のfixtureとJSONの例へ`resultStatus`を、`kind`が`file`の`source`へ`workspaceId`を追加する必要がある。

## Alternatives

1. **診断コードの表から結果の状態を逆引きする**: 条件によって結果の状態が変わる診断コードでは、個々の診断を判別できないため採用しない。
2. **`source.path`をリポジトリのルート相対にする**: 単一ワークスペースの結果との互換性と所有境界を崩すため採用しない。
3. **操作ごとに集約の順序を定義する**: 新しい操作を追加したときに、差異が再発するため採用しない。

## Notes

- 本ADRはADR-021を変更せず、実行時のスキーマと集約の規則を補完する。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | Diagnostic結果効果、共通集約、workspace sourceを確定 | — |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
