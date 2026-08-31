---
id: ADR-011
title: Diagnostic所有者とコード命名規約
status: accepted
relations:
  related:
    - ADR-003
    - ADR-009
---

# ADR-011 Diagnostic所有者とコード命名規約

## Context

ADR-003はDiagnosticの正本を旧`bitz-env`へ置き、コードを3セグメント固定としていた。ADR-009で旧構成を
廃止した後も、EARS-AIとSPEC詳細設計の一部がADR-003を参照していた。一方、現行コードは
`EAI-CORE-SYNTAX-001`や`SPEC-CONFIG-SCHEMA-001`の4セグメントを使用している。

## Decision

1. Diagnostic共通スキーマとCore OWNER一覧は`bitz-core`が所有する。
2. Coreは`EAI`、`SPEC`、`CTX`を予約OWNERとする。
3. Coreコードは`<OWNER>-<AREA>-<CATEGORY>-<NNN>`を基本形とする。
4. Profileは所有プラグインのOWNERを使い、`<OWNER>-<CATEGORY>-<NNN>`の3セグメントを使用してよい。
5. コードは永続識別子とし、公開後の再利用と意味変更を禁止する。
6. Diagnostic一覧は各規範文書が条件とseverityを定義し、共通フィールドと終了コードだけを
   `bitz-core`の共通スキーマへ集約する。

### 理由

- 実在するコード体系と規約を一致させる。
- 小規模コアのために別のOWNERレジストリサービスを必要としない。
- 診断から所有領域を判別でき、Profileの短いコードも維持できる。

## Consequences

- ADR-003のDiagnostic所有者と3セグメント固定規則を現在の設計判断に使用しない。
- EARS-AI Core/ProfileとSPEC規定は本ADRを参照する。
- 新しいCoreコードは4セグメントを既定とする。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-25 | 初版を作成 | — |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
