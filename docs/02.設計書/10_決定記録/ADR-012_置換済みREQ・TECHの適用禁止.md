---
id: ADR-012
title: 置換済みREQ・TECHの適用禁止
status: accepted
relations:
  related:
    - ADR-010
---

# ADR-012 置換済みREQ・TECHの適用禁止

## Context

REQとTECHの状態は`draft`、`approved`、`outdated`の3つに限定している。一方、後継文書が
`supersedes`で旧文書を置換しても、旧文書は`approved`のまま残るため、旧要求を目的`implement`または`verify`の
起点にできる穴があった。

## Decision

1. REQとTECHへ状態`superseded`を追加しない。
2. 有効な後継文書から`supersedes`されているREQとTECHを、逆参照により論理的な置換済み文書と判定する。
3. 置換済みのREQまたはTECHを、目的`implement`または`verify`の起点・強い依存先にした操作は`blocked`とする。
4. 目的`interpret`では旧文書を参考として返し、有効な後継文書を明示する。
5. 同じ旧文書に複数の有効な後継がある場合は曖昧な置換として`failed`にする。
6. Coreは後継へ暗黙に起点を差し替えない。利用者またはエージェントが後継IDを明示して再実行する。

### 理由

- 状態機械を増やさず、旧要求の誤実装を防止できる。
- 自動差替えによる意図しない意味変更を避けられる。
- Git履歴と`supersedes`の関係だけで置換理由を追跡できる。

## Consequences

- コンテキスト解決器は`supersedes`の逆索引を持つ。
- `CTX-STATE-SUPERSEDED-001`と`CTX-STATE-SUPERSEDED-002`を追加する。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-25 | 初版を作成 | — |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
