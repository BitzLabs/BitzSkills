# ADR-013: 文書IDとローカルIDの字句規則訂正

- 状態: Accepted
- 決定日: 2026-08-25
- Amends: ADR-005

## 背景

ADR-005は文書IDを3桁以上とする意図だったが、EARS-AI Core構文には3桁固定の規則が残っていた。
またADR-005の`local-id`は先頭ハイフンを許す一方、Core構文は英数字始まりとしており、実装差が生じる状態だった。

## 決定

```text
document-id = prefix, "-", 3*DIGIT
local-id = ALNUM, *( ALNUM / "-" )
statement-id = document-id, ":", local-id
```

- 文書IDの数字部分は3桁以上とする。
- ローカルIDは英数字で開始し、先頭・末尾ハイフンと連続ハイフンを推奨しない。
- Core 1.0の配置可能な文書prefixは`REQ`、`TECH`、`ADR`、`TASK`とする。

## 理由

- `REQ-1000`以降も同じ規則で扱える。
- ローカルIDの先頭を固定するとLexerと正規表現が一致する。
- Deferred Profileの概念名とCore文書種別を混同しない。
