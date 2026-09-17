---
id: ADR-047
title: 複合workspaceの識別子をmultiWorkspaceへ改名する
status: accepted
relations:
  requires:
    - ADR-040
    - ADR-042
    - ADR-043
  related:
    - ADR-046
---

# ADR-047 複合workspaceの識別子をmultiWorkspaceへ改名する

## Context

[用語集](../../用語集.md)の表記統一で、複数のworkspaceを束ねる構成を本文では「複合workspace」、
1つだけの構成を「単一workspace」と呼ぶことにした。一方、識別子はADR-040〜043で定めた`monorepo`（設定key、
Capability、Diagnostic code）と`federation`（結果JSONのfield、継続単位の語彙）が混在し、fixture IDは`MONO-*`である。
本文の名前と識別子が3種類に分かれると、読み手が同じ構成を指していると判断しにくい。

`monorepo`はrepositoryの形態を表す語であり、Coreの機能は1つのrepository内で複数のworkspaceを束ねることにある。
Core 1.0は未リリースで、これらの識別子を公開したことはない。

## Decision

1. 複合workspaceを表す識別子を次のとおり改める。

   | 種類 | 旧 | 新 |
   |---|---|---|
   | 設定key | `monorepo`、`monorepo.members`、`monorepo.maxMembers` | `multiWorkspace`、`multiWorkspace.members`、`multiWorkspace.maxMembers` |
   | Capability | `monorepo.v1` | `multiWorkspace.v1` |
   | 結果JSONのfield | `federation` | `multiWorkspace` |
   | Diagnostic code | `SPEC-MONOREPO-*` | `SPEC-MULTI-*` |
   | Diagnostic registryのcondition ID | `MONO-*` | `MULTI-*` |
   | 継続単位の語彙 | `stop-federation` | `stop-multi-workspace` |
   | 適合fixture IDとdirectory | `MONO-NNN`、`fixtures/conformance/monorepo/` | `MULTI-NNN`、`fixtures/conformance/multi/` |
   | 性能datasetの種別とID | `federation`、`core-federation-v1` | `multiWorkspace`、`core-multi-workspace-v1` |

2. 操作の範囲やedgeの性質を表す識別子は変えない: `--all-workspaces`、`scope: all-workspaces`、
   `crossWorkspaceEdges`、`workspaces`、`workspaceId`、`SINGLE-NNN`。
3. condition IDは本来、名称変更と再利用を禁止する永続IDである。本改名はCore 1.0の公開前に限る一回だけの例外とし、
   公開後は同じ理由でも改名しない。旧ID `MONO-*`を別の条件へ再利用しない。
4. 意味、severity、status、継続単位、優先順位、結果JSONの外形規則は変えない。全体結果は
   `workspace`を持たず`multiWorkspace`と`workspaces`を持つ外形で識別する。
5. 既存ADRと、裁定済みの提案資料の本文は当時の識別子のまま残す。現行の規範は`docs/03.詳細設計`とfixtureを正とする。

## Consequences

- 本文の「複合workspace」と識別子の`multiWorkspace`が対応し、同じ構成を1つの名前で追跡できる。
- 公開前の改名なので、旧識別子を読む移行層を設けない。
- doctorの期待結果に含むCapability一覧、性能datasetの生成物と期待tree digest、Diagnostic台帳が変わる。
  これらは本ADRと同じ変更で更新し、再review記録を残す。
- ADR-040〜043と裁定済みの提案資料には旧識別子が残る。読むときは本ADRの対応表で読み替える。

## Alternatives

1. **`multi`へ統一する**: 短いが、設定key単体では何が複数なのかが分からない。採用しない。
2. **`federation`へ統一する**: 結果JSONとは揃うが、本文の「複合workspace」と対応しない。採用しない。
3. **識別子を変えず本文だけを統一する**: 変更量は最小だが、本文と識別子の名前が3種類に分かれたまま残る。採用しない。
4. **`--all-workspaces`も`multiWorkspace`系へ改める**: optionは構成ではなく操作の範囲を表し、単一workspaceの
   `--workspace`とも対になっている。採用しない。
5. **既存ADRと提案資料の本文も書き換える**: 決定時点の記録を変えることになる。採用しない。

## Notes

- 反映先: [用語集 §4.7](../../用語集.md)、[workspace・設定仕様](../../03.詳細設計/02_SPECモデル/01_workspace・設定仕様.md)、
  複合workspace仕様（`docs/03.詳細設計/02_SPECモデル/`）、[結果・Diagnostic・終了コード](../../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)、
  [Diagnostic registry](../../03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
  [適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、[doctor仕様](../../03.詳細設計/03_操作仕様/04_doctor.md)、
  [運用手順](../04_運用手順.md)、`fixtures/`配下のSchema、期待結果、性能dataset。
- ADR-040、ADR-042、ADR-043、ADR-044、ADR-046のNotesとRevision Historyへ、本ADRによる識別子の改名を記録した。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-17 | 複合workspaceの識別子を`multiWorkspace`、`SPEC-MULTI-*`、`MULTI-*`へ改名 | 用語集 §4.7 |
