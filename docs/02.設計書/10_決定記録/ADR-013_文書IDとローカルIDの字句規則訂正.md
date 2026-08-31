---
id: ADR-013
title: 文書IDとローカルIDの字句規則訂正
status: accepted
relations:
  related:
    - ADR-005
---

# ADR-013 文書IDとローカルIDの字句規則訂正

## Context

ADR-005は文書IDを3桁以上とする意図だったが、EARS-AI Core構文には3桁固定の規則が残っていた。
またADR-005の`local-id`は先頭ハイフンを許す一方、Core構文は英数字始まりとしており、実装差が生じる状態だった。

## Decision

```text
document-id = prefix, "-", 3*DIGIT
local-id = ALNUM, *( ALNUM / "-" )
statement-id = document-id, ":", local-id
```

- 文書IDの数字部分は3桁以上とする。
- ローカルIDは英数字で開始し、先頭・末尾ハイフンと連続ハイフンを推奨しない。
- Core 1.0の配置可能な文書prefixは`REQ`、`TECH`、`ADR`、`TASK`とする。

### 理由

- `REQ-1000`以降も同じ規則で扱える。
- ローカルIDの先頭を固定するとLexerと正規表現が一致する。
- Deferred Profileの概念名とCore文書種別を混同しない。

## Consequences

- ADR-005のEBNFは本ADRで訂正され、実装はEARS-AI Core構文仕様を正とする。
- EARS-AI Core構文仕様、配置・命名規則、ADR-005の3文書が同じ字句規則を指す。
- `DOMAIN`や`RULE`などDeferred Profileの概念名は、Core 1.0の文書prefixとして使用できない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-25 | 初版を作成 | — |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
