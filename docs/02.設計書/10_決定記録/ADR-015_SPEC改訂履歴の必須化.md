---
id: ADR-015
title: SPEC改訂履歴の必須化
status: accepted
relations:
  related:
    - ADR-014
---

# ADR-015 SPEC改訂履歴の必須化

## Context

従来設計は、成果物ごとの`version`、`updated`、`Revision History`をGit履歴との重複として採用しなかった。
しかしGitのcommit一覧とdiffだけでは、仕様契約がなぜ改訂されたかを文書単体から短時間で把握しにくい。
AIへ段階的なContextを渡す場合も、全文やGit履歴を展開せずに主要な改訂意図を確認できる入口が必要である。

一方、文書内の履歴を完全な監査台帳にするとGitとの同期ずれを再び生む。文書側の役割を人間向け要約に限定し、
正確な証跡との責務を分離する必要がある。

## Decision

1. REQ、TECH、ADR、TASKの最終H2に`Revision History`を必須とする。
2. 表は`Date`、`Summary`、`Reference`の3列固定とし、初版から1行以上を記載する。
3. `Revision History`は主要な契約、境界、判断の改訂意図を要約する。正確な差分、変更者、commit時刻は
   引き続きGit履歴を正とする。
4. 成果物ごとの独自`version`や`updated`は導入しない。
5. 承認済みREQの意味変更、TECHの契約変更、TASKの作業境界変更では、同じ変更で履歴行を追記する。
6. 履歴追記はstatus遷移、承認保護、後継ADR、レビューを代替しない。
7. ADRのDecisionを変更する場合は後継ADRを作る。旧ADRの履歴には作成、非意味的訂正、後継化だけを要約する。
8. `Revision History`は非規範メタデータとし、Constraint Ledger、coverage、Context Digestの意味集合から除外する。
9. Context BundleのJSONは最新1件と件数だけをManifestへ載せる。LLM向け表示は`interpret`の起点・直接文書だけに
   最新要約を示し、`implement`と`verify`では既定表示しない。全履歴は明示展開時だけ返す。
10. Coreは履歴を除く`semanticHash`と、履歴を含む`fileHash`を分離する。

## Consequences

- 文書単体で主要な改訂理由と関連する裁定を把握できる。
- 新規SPECには初版行の記述コストが加わる。
- Coreは必須H2、最終位置、表の列、1行以上の履歴を構造検査する。
- Git履歴と文書内要約の内容が異なる場合、Gitの差分と参照先を事実の正とする。
- 既存SPECはCore 1.0適合前に`Revision History`を追加する必要がある。
- 履歴だけの訂正はContext Digestを失効させず、LLMの通常コンテキストを希釈しない。

## Alternatives

1. **Git履歴だけを使う**: 正確だが、文書単体から改訂意図を把握しにくい。
2. **Frontmatterへversionとupdatedを追加する**: 機械更新項目が増え、内容との同期ずれを生む。
3. **任意セクションにする**: 重要な文書ほど履歴の有無がばらつき、共通の参照位置にならない。
4. **完全な変更台帳を本文へ複製する**: Gitと責務が重なり、記述・同期コストが過大になる。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-27 | 初版を作成 | — |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
