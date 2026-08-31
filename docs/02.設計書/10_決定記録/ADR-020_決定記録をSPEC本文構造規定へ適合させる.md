---
id: ADR-020
title: 決定記録をSPEC本文構造規定へ適合させる
status: accepted
relations:
  related:
    - ADR-015
---

# ADR-020 決定記録をSPEC本文構造規定へ適合させる

## Context

`02.設計書/10_決定記録/`は、自らを「Bitz AI-SDDプラグイン群自身の開発に対する
`.spec/decisions/`相当物」と定義している。しかし適合前の18件のADRはFrontmatterを持たず、
H2構成は8種類に分かれ、`Revision History`を1件も持たなかった。

ADR-015は「既存SPECはCore 1.0適合前に`Revision History`を追加する必要がある」と定めており、
本ディレクトリはその対象である。規定を実文書へ適用しないまま実装へ進むと、
`SPEC-STYLE-*`が実際の文書に対してどれだけ発火するかを出荷前に測れない。

## Decision

1. 決定記録の全ADRへFrontmatter（`id`、`title`、`status`、`relations`）を追加する。
   状態は[補助SPEC仕様](../../03.詳細設計/02_SPECファイル規定/05_補助SPEC仕様.md) §3の
   小文字語彙を使い、状態と後継関係はFrontmatterを正とする。
2. H1を`# <id> <title>`、H2を`Context`、`Decision`、`Consequences`、任意の`Alternatives`、
   `Notes`、最終H2の`Revision History`へ統一する。
3. 既存の理由・採用理由・性能判断・必須の実装制約はH3として`Decision`の下へ収める。
   本文冒頭にあった関連文書リンクは`Notes`へ移す。
4. `Amends`、`Clarifies`に対応する型付き語彙はCoreにないため`related`で表す。
   `Superseded by`は後継ADRの`supersedes`からの逆参照とし、旧ADR側には書かず、
   後継化の事実を旧ADRの`Revision History`へ1行で残す。
   改訂関係の機械追跡が実測で必要になった場合に、新しい関係型を別途裁定する。
5. `.spec/`の配置・命名・探索規則は適用しない。本ディレクトリは`docs/`配下の設計資料であり、
   ファイル名の改名は27文書67リンクの書換えを伴う一方、得られる検証価値がない。
6. 適合後のADRを、`SPEC-STYLE-*`と`SPEC-RELATION-*`の正例fixtureとして
   [実装ロードマップ](../08_実装ロードマップ.md) Phase 1へ加える。

## Consequences

- 本文構造規定を、実装前に20件の実文書で検証できる。
- ADRの状態と後継関係が、本文の箇条書きではなくFrontmatterから機械的に読める。
- 新規ADRの作成コストへ、Frontmatterと初版履歴行が加わる。
- 本ディレクトリは配置とファイル名の2点で`.spec/`規定と異なる。この差はREADMEへ明記する。
- 適合前の8種類のH2構成は、`SPEC-STYLE-SECTION-002`の反例fixtureとしてGit履歴から取得できる。
- `Consequences`を持たなかったADR-006とADR-013へ、本適合の一部として節を追記した。

## Alternatives

1. **規定の適用対象外と明記する**: READMEから「`.spec/decisions/`相当物」を削除すれば
   矛盾は消えるが、Core 1.0出荷前に規定を実文書で検証する唯一の機会を失う。
2. **ファイル名も`<ID>-<slug>.md`へ改名する**: 27文書67リンクの書換えが必要な一方、
   区切り文字の統一から得られる検証価値は小さい。
3. **`amends`関係型をCoreへ追加する**: 実測のない語彙追加であり、
   Coreを小さく保つ原則（[EARS-AI規格](../../03.詳細設計/01_EARS-AI規格/README.md) §5-1）に反する。

## Notes

本ADRは[04.提案資料/03_設計書・詳細設計レビューと改訂提案.md](../../04.提案資料/03_設計書・詳細設計レビューと改訂提案.md)
§3.7に対する裁定であり、同書 附録B.7の手順で適用した。

Decision 4のうち、`Amends`相当を`related`だけで表すとした部分は
[ADR-033](ADR-033_部分改訂ADRの記録規約.md)が置き換えた。部分改訂は`related`に加えて、後継ADRの
Decision本文、旧ADRの`Notes`、旧ADRの`Revision History`の3点で記録する。同Decision後段の
「改訂関係の機械追跡が実測で必要になった場合に新しい関係型を裁定する」は維持されている。
本ADRの他のDecisionは変更されていない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | 初版を作成 | `ADR-015` |
| 2026-08-31 | Decision 4の`Amends`表現を`ADR-033`が部分改訂 | `ADR-033` |
