---
id: ADR-044
title: MCP面をCore 1.0のscope外とする
status: accepted
relations:
  requires:
    - ADR-009
    - ADR-016
  related:
    - ADR-039
---

# ADR-044 MCP面をCore 1.0のscope外とする

## Context

詳細設計と操作仕様は「CLI/MCP入力」の所有を宣言し、Diagnosticの`source.kind: invocation`は
「CLI/MCP呼出し」を用途とし、doctorは`SPEC-DOCTOR-CORE-002`を「Core/MCP起動不能」として定義している。

しかし、MCP serverとしてのtool名、tool ごとの入力Schema、結果の返し方、transport、
Capability名との対応、認可と信頼境界はどの正本にも存在しない。4か所の記述が実体のない面を
参照している状態であり、実装者はMCP面を実装すべきか判断できない。

MCP面をCore 1.0へ含める場合、CLIと同等の入力・対象選択・結果・Diagnostic契約が新規に必要になる。
これは操作仕様4本と同規模の追加であり、[ADR-039](ADR-039_Core-1.0仕様構造の再編とscope縮小.md)が
確定した「Core 1.0を垂直スライスへ戻す」方針と整合しない。

一方でCore 1.0の公開面はCLIとJSON結果で閉じている。adapterとSkillは
[システム構成 §2](../01_システム構成.md)のとおりCoreの構造化結果を説明する層であり、
MCP serverが必要な場合はadapter側がCLIのJSON結果を包めば足りる。Coreへ第2の入力面を持たせる
必要性は実測で確認されていない。

## Decision

1. Core 1.0の公開面はCLIと`--format json`の結果だけとする。CoreはMCP serverを提供しない。
2. MCP serverが必要な場合はadapterまたは独立拡張の責務とし、Coreの公開操作と共通結果契約へ依存させる。
   adapterはCoreの内部moduleとcacheへ依存しない。
3. 詳細設計README、操作仕様README、`source.kind`の用途記述から「MCP」の語を外し、
   CLIとadapter呼出しを指す語へ改める。`source.kind: invocation`はCLI引数とadapterからの
   呼出し引数の双方を表す。
4. `SPEC-DOCTOR-CORE-002`は「Core実行体を起動できない」条件のcodeとして維持し、
   MCP起動の判定には使用しない。code、severity、`resultStatus`は変更しない。
5. Capability `context.v1`、`check.v1`、`verify.v1`、`doctor.v1`、`monorepo.v1`はCLI公開操作の
   機能単位であり、transportを含意しない。この意味を変えない。
6. MCP面をCore 1.1以降へ追加する場合は、操作仕様と同等の入力・結果・Diagnostic契約と
   適合fixtureを伴う新しいADRから開始する。Core 1.0のCLI契約を後から流用可能とは仮定しない。

## Consequences

- 実体のない公開面への参照が正本から消え、実装者はCLIだけを実装対象として読める。
- MCP clientから使う利用者はadapter層を必要とする。Coreだけでは接続できない。
- Capabilityの意味がtransportから独立し、`monorepo.v1`の確認手順が変わらない。
- 将来MCPを追加する際、CLI固有の引数不正（終了コード4）に相当する契約を別途定義する必要がある。
  この負債は本決定によって生じるものではなく、もともと未定義だったものを明示したにすぎない。

## Alternatives

1. **Core 1.0でMCP serverを提供する**: tool Schema、transport、認可、結果の返し方、
   引数不正の扱いを新規に確定する必要があり、操作仕様4本と同規模の追加になる。ADR-039のscope縮小と
   両立せず、実測による必要性の確認もない。採用しない。
2. **記述を残したまま実装を保留する**: 「所有する」と書かれた契約が存在しない状態が続き、
   1規則1正本の原則に反する。実装者が面の有無を判断できないため採用しない。
3. **MCPをCapabilityとして予約だけする**: 予約したCapability名は`doctor`の
   `--require-capability`で要求できてしまい、常に不足として`blocked`を返す。
   利用者から見て機能があるように見えるため採用しない。

## Notes

- 本ADRは[提案24](../../04.提案資料/24_Core-1.0実装着手方針.md) G5に対する裁定である。
- 反映先: [03.詳細設計/README](../../03.詳細設計/README.md)、
  [操作仕様/README](../../03.詳細設計/03_操作仕様/README.md)、
  [結果・Diagnostic・終了コード](../../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)、
  [doctor仕様](../../03.詳細設計/03_操作仕様/04_doctor.md)。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-03 | MCP面をCore 1.0のscope外とし、公開面をCLIとJSON結果へ限定 | 提案24 G5 |
