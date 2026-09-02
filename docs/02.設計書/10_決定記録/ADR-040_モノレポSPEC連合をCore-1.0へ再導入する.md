---
id: ADR-040
title: モノレポSPEC連合をCore 1.0へ再導入する
status: accepted
relations:
  requires:
    - ADR-009
    - ADR-010
    - ADR-021
    - ADR-025
  related:
    - ADR-017
    - ADR-039
---

# ADR-040 モノレポSPEC連合をCore 1.0へ再導入する

## Context

ADR-017は、1つのGit repositoryにある複数の`.spec/`を明示的な連合として扱う設計を採用した。その後、
ADR-039はCore 1.0の最小垂直スライスを先に実証するため、連合を1.1以降へ延期した。

しかし、実際の導入単位にはWeb、API、libraryなど複数の所有境界を持つモノレポが含まれる。単一root `.spec/`へ
全要求、設定、test commandを集約すると、各projectの独立性、Context上限、変更pathの所有責任をCore 1.0で
検証できない。利用開始後にworkspace ID、修飾参照、結果Schemaを追加すると、1.0で作成したSPECとadapterへ
より大きな互換性影響を与える。

一方、ADR-039で行った文書責務の分割、command名単位のverify、単一Context Digest、Profile実行基盤の延期は、
連合とは独立して有効である。旧仕様全体を戻すのではなく、連合固有契約を1文書へ隔離してCore 1.0へ含める。

## Decision

1. Core 1.0は、単一workspaceに加え、1つのGit repository内にある複数workspaceの明示的なSPEC連合を扱う。
   Git repository rootの`.spec/bitz.yaml`をfederation rootとし、`monorepo.members`へmemberの`id`と`path`を
   列挙する。暗黙の再帰探索、glob、nested federation、Git submodule、別repositoryは対象外とする。
2. 文書IDはworkspace内で一意とする。連合内の正規参照は`<workspace-id>::<document-id>`、規範文参照は
   `<workspace-id>::<document-id>:<local-id>`とする。workspaceを越える参照と連合内の機械結果は修飾形式を
   使用し、探索順による暗黙解決を禁止する。
3. memberは自身の設定、SPEC、code、test、TASK変更pathを所有する。member同士のpath重複と入れ子を禁止し、
   federation rootは登録member配下のcodeとtestを直接所有しない。設定はworkspace間で継承しない。
4. 通常操作はactive workspaceを1つ選ぶ。`--workspace`は連合catalogから明示選択する。
   `check`、`verify`、`doctor`はfederation rootで`--all-workspaces`を受け付ける。全体操作はrootを先頭、
   memberをworkspace ID辞書順で逐次処理し、結果を共通statusの最悪値規則で集約する。
5. 横断Contextは起点から強い関係で到達するworkspaceだけを完全解決する。起点workspaceのContext上限を適用し、
   到達workspaceのID、path、実効設定、修飾edgeをContext Digestへ含める。未到達memberの本文と設定は含めない。
6. verify bindingはADR-039 Decision 10どおりcommand名で識別する。連合での実行単位は
   `(workspaceId, commandName)`とし、異なるworkspaceのcommandを統合しない。testは所有workspaceの設定と`cwd`で
   実行する。旧ADR-030のargv/cwd内容同一性による統合は復活させない。
7. Core 1.0は`monorepo.v1` Capabilityを公開する。Gitは単一workspaceでは引き続き縮退可能だが、連合では
   repository境界、member、所有範囲を確定する前提であるため、利用できなければ連合操作を`blocked`にする。
8. member既定上限は20、hard limitは100とし、SPEC file 10,000件の上限は連合全体へ適用する。
   ID自動改番、Profile実行基盤、公開hash追加、必須Revision History、厳格style検査は再導入しない。
9. 本決定はADR-039 Decision 5と、それに対応するConsequences、Notesのモノレポ延期部分だけを置き換える。
   ADR-039の他のDecisionは変更しない。ADR-017は旧構造に基づく履歴として`superseded`のまま保持し、現在の
   機械契約は再編後の詳細設計に置く。

## Consequences

- projectごとに自己完結したSPECとtest commandを維持しつつ、共通要求を決定論的に追跡できる。
- workspace、修飾ID、所有境界、集約結果が1.0の公開契約となり、単一workspaceの結果にも将来追加の揺れが減る。
- 連合catalog、横断索引、所有検査、全体操作のfixtureと性能試験がCore 1.0の実装対象へ加わる。
- 通常Contextは依存到達範囲に限定されるため、モノレポ全体の本文をLLMへ投入しない。
- Gitを持たないdirectoryでは単一workspaceだけを利用でき、連合機能は利用できない。
- 1.0のscopeは広がるが、連合固有規則を独立仕様へ集約し、各操作仕様には公開引数と操作固有差分だけを置く。

## Alternatives

1. **ADR-039どおり1.1まで延期する**: 初期実装は小さくなるが、対象モノレポで単一root `.spec/`への集約を
   強制し、1.1移行時にID、参照、結果Schemaを変更するため採用しない。
2. **repositoryに1つの巨大な`.spec/`だけを置く**: 既存Coreで動くが、設定、test command、ID、所有境界が
   集中し、project単位のContextと責任分離を失うため採用しない。
3. **`.spec/`を再帰探索して自動連合する**: 導入設定は減るが、fixture、vendor、submoduleを意図せず取り込み、
   入力と信頼境界が不安定になるため採用しない。
4. **旧ADR-017と旧詳細仕様をそのまま復元する**: 既に簡素化されたverify binding、Profile、hash、文書構造まで
   巻き戻して矛盾を再導入するため採用しない。
5. **複数Git repositoryも同時に扱う**: 認証、network、version pin、可用性という別の信頼境界が必要なため
   Core 1.0には含めない。

## Notes

- 現行契約は[モノレポSPEC連合仕様](../../03.詳細設計/02_SPECモデル/05_モノレポSPEC連合仕様.md)を含む
  `docs/03.詳細設計`に記載する。
- ADR-039のS2〜S7に対応する簡素化と、1規則1正本の文書構造は維持する。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-02 | 現行の簡素化を維持してモノレポSPEC連合をCore 1.0へ再導入 | ADR-017, ADR-039 |
