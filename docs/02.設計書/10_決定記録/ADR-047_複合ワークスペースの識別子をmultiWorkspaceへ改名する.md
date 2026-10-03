---
id: ADR-047
title: 複合ワークスペースの識別子を`multiWorkspace`へ改名する
status: accepted
relations:
  requires:
    - ADR-040
    - ADR-042
    - ADR-043
  related:
    - ADR-046
---

# ADR-047 複合ワークスペースの識別子を`multiWorkspace`へ改名する

## Context

[用語集](../../用語集.md)の表記統一で、複数のワークスペースを束ねる構成を、本文では「複合workspace」、
1つだけの構成を「単一workspace」と呼ぶことにした。一方、識別子は、ADR-040〜043で定めた`monorepo`（設定キー、
対応機能、診断コード）と`federation`（結果のJSONのフィールド、継続単位の語彙）が混在し、fixture IDは`MONO-*`である。
本文の名前と識別子が3種類に分かれると、読み手が同じ構成を指していると判断しにくい。

`monorepo`はリポジトリの形態を表す語であり、Coreの機能は、1つのリポジトリ内で複数のワークスペースを束ねることにある。
Core 1.0は未リリースで、これらの識別子を公開したことはない。

## Decision

1. 複合ワークスペースを表す識別子を、次のとおり改める。

   | 種類 | 旧 | 新 |
   |---|---|---|
   | 設定キー | `monorepo`、`monorepo.members`、`monorepo.maxMembers` | `multiWorkspace`、`multiWorkspace.members`、`multiWorkspace.maxMembers` |
   | 対応機能 | `monorepo.v1` | `multiWorkspace.v1` |
   | 結果のJSONのフィールド | `federation` | `multiWorkspace` |
   | 診断コード | `SPEC-MONOREPO-*` | `SPEC-MULTI-*` |
   | 診断レジストリの条件ID | `MONO-*` | `MULTI-*` |
   | 継続単位の語彙 | `stop-federation` | `stop-multi-workspace` |
   | 適合fixtureのIDとディレクトリ | `MONO-NNN`、`fixtures/conformance/monorepo/` | `MULTI-NNN`、`fixtures/conformance/multi/` |
   | 性能データセットの種別とID | `federation`、`core-federation-v1` | `multiWorkspace`、`core-multi-workspace-v1` |

2. 操作の範囲またはエッジの性質を表す識別子は変えない: `--all-workspaces`、`scope: all-workspaces`、
   `crossWorkspaceEdges`、`workspaces`、`workspaceId`、`SINGLE-NNN`。
3. 条件IDは、本来、名称の変更と再利用を禁止する永続的なIDである。本改名はCore 1.0の公開前に限る一回だけの例外とし、
   公開後は同じ理由でも改名しない。旧ID`MONO-*`を別の条件へ再利用しない。
4. 意味、重大度、結果への効果、継続単位、優先順位、結果のJSONの外形の規則は変えない。全体結果は、
   `workspace`を持たず`multiWorkspace`と`workspaces`を持つ外形で識別する。
5. 既存のADRと、裁定済みの提案資料の本文は、当時の識別子のまま残す。現行の規範は、`docs/03.詳細設計`とfixtureを正とする。

## Consequences

- 本文の「複合workspace」と識別子の`multiWorkspace`が対応し、同じ構成を1つの名前で追跡できる。
- 公開前の改名なので、旧識別子を読む移行層を設けない。
- `doctor`の期待結果に含まれる対応機能の一覧、性能データセットの生成物と期待する木構造のハッシュ値、診断の網羅表が変わる。
  これらは本ADRと同じ変更で更新し、再レビューの記録を残す。
- ADR-040〜043と、裁定済みの提案資料には、旧識別子が残る。読むときは、本ADRの対応表で読み替える。

## Alternatives

1. **`multi`へ統一する**: 短いが、設定キー単体では何が複数なのかが分からない。採用しない。
2. **`federation`へ統一する**: 結果のJSONとはそろうが、本文の「複合workspace」と対応しない。採用しない。
3. **識別子を変えず、本文だけを統一する**: 変更量は最小だが、本文と識別子の名前が3種類に分かれたまま残る。採用しない。
4. **`--all-workspaces`も`multiWorkspace`系へ改める**: オプションは構成ではなく操作の範囲を表し、単一ワークスペースの
   `--workspace`とも対になっている。採用しない。
5. **既存のADRと提案資料の本文も書き換える**: 決定した時点の記録を変えることになる。採用しない。

## Notes

- 反映先: [用語集 §4.7](../../用語集.md)、[ワークスペース・設定仕様](../../03.詳細設計/02_仕様文書モデル/01_ワークスペース・設定仕様.md)、
  複合ワークスペース仕様（`docs/03.詳細設計/02_仕様文書モデル/`）、[結果・診断・終了コード](../../03.詳細設計/00_共通契約/01_結果・診断・終了コード.md)、
  [診断レジストリ](../../03.詳細設計/00_共通契約/05_診断レジストリ.md)、
  [適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、[`bitz doctor`仕様](../../03.詳細設計/03_操作仕様/04_doctor.md)、
  [運用手順](../04_運用手順.md)、`fixtures/`配下のスキーマ、期待結果、性能データセット。
- ADR-040、ADR-042、ADR-043、ADR-044、ADR-046の`Notes`と`Revision History`へ、本ADRによる識別子の改名を記録した。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-17 | 複合workspaceの識別子を`multiWorkspace`、`SPEC-MULTI-*`、`MULTI-*`へ改名 | 用語集 §4.7 |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
