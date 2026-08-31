# ADR-012: 置換済みREQ・TECHの適用禁止

- 状態: Accepted
- 決定日: 2026-08-25
- Amends: ADR-010

## 背景

REQ/TECHの状態は`draft`、`approved`、`outdated`の3つに限定している。一方、後継文書が
`supersedes`で旧文書を置換しても、旧文書は`approved`のまま残るため、旧要求を`implement`や`verify`の
起点にできる穴があった。

## 決定

1. REQ/TECHへ`superseded`状態を追加しない。
2. 有効な後継文書から`supersedes`されているREQ/TECHを、逆参照により論理的な置換済み文書と判定する。
3. 置換済みREQ/TECHを`implement`または`verify`の起点・強い依存先にした操作は`blocked`とする。
4. `interpret`では旧文書をadvisoryとして返し、有効な後継文書を明示する。
5. 同じ旧文書に複数の有効な後継がある場合は曖昧な置換として`failed`にする。
6. Coreは後継へ暗黙に起点を差し替えない。利用者またはエージェントが後継IDを明示して再実行する。

## 理由

- 状態機械を増やさず、旧要求の誤実装を防止できる。
- 自動差替えによる意図しない意味変更を避けられる。
- Git履歴と`supersedes`関係だけで置換理由を追跡できる。

## 影響

- Context Resolverは`supersedes`の逆索引を持つ。
- `CTX-STATE-SUPERSEDED-001`と`CTX-STATE-SUPERSEDED-002`を追加する。
