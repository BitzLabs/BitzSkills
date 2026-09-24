---
id: ADR-050
title: 契約Schemaの正本を詳細設計へ置く
status: accepted
relations:
  requires:
    - ADR-045
    - ADR-049
  related:
    - ADR-046
---

# ADR-050 契約Schemaの正本を詳細設計へ置く

## Context

公開JSON結果のSchema（`result.schema.json`）とFrontmatterのSchema（`frontmatter.schema.json`）は、
[結果・Diagnostic・終了コード §1](../../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#1-所有範囲)と
[文書・Frontmatter・状態仕様 §2](../../03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#2-frontmatter)が
機械可読な正本として参照する契約である。これらは`fixtures/conformance/`に置かれていた。
この配置には次の問題がある。

1. 契約の正本が、それを検査する側のdirectoryにある。仕様から試験への依存の向きが逆になる。
2. [ADR-049](ADR-049_Coreのsource配置と試験の構成を確定する.md) Decision 6により、`plugins/bitz-core`は`fixtures/`を参照しない。
   Frontmatter仕様は「Coreは同Schemaの定義を選んで検証する」としていたが、Coreは正本を読めない。
3. [ADR-045](ADR-045_実行環境と配布物の確定.md) Decision 3により、Coreのruntime依存は標準libraryとYAML library 1つに限られ、
   JSON Schema validatorを使えない。Schema fileを読めたとしても、そのまま評価する手段がない。

正本をCore packageへ移すと、Gate Bで検査される側が検査の基準を持つことになる。Coreの変更がSchemaを緩めても
合格し得る。[ADR-046](ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)がpackage検査を
`bitz.compat`へ含める案を自己申告として採らなかったのと同じ構造である。

## Decision

1. **正本の配置**: `result.schema.json`と`frontmatter.schema.json`の正本を`docs/03.詳細設計/schemas/`へ置く。
   [詳細設計](../../03.詳細設計/README.md)がCore 1.0の機械契約の正本であることに合わせる。
2. **fixture形式のSchema**: fixture自身の形式を定める`manifest.schema.json`と`side-effects.schema.json`は、
   `fixtures/conformance/`に残す。
3. **参照の向き**: `fixtures/`と`tests/`は契約Schemaを`docs/03.詳細設計/schemas/`から読み、写しを持たない。
   Gate A・Bで期待値とCoreの出力を検査する基準は、この正本だけとする。
4. **Coreでの扱い**: Coreは契約Schemaと同じ判定を行う。Schema fileを実行時に読むこと、JSON Schema validatorを
   使うことは要求しない。Frontmatter仕様 §2の「定義を選んで検証する」はこの意味とする。
5. **Coreへの同梱**: 将来Core packageへSchemaを同梱する場合は、plugin directory内に写しを置き、
   写しが正本とbyte一致することを`fixtures/`または`tests/`の側で検査する。写しを正本にしない。

## Consequences

- 詳細設計の本文と、その機械可読な正本が同じdirectoryにそろう。表・例とSchemaの同時修正を確認しやすくなる。
- fixtureの検証器は、Schemaの場所を`fixtures/conformance/schemas.py`の`schema_path`で解決する。
  契約Schemaは常に正本から読み、fixture形式のSchemaはfixtureのrootから読む。
- Coreは、Frontmatterと結果外形の判定を標準libraryで実装する。判定と正本の一致は、適合fixtureと
  Gate Bで確認する。
- 配置の変更でGate Aの認定対象の内容が変わるため、`certify_gate_a.py`で再認定する。
- `docs/`はMarkdownの設計資料だけでなく、機械可読なSchemaも持つ。

## Alternatives

1. **`fixtures/conformance/`に残す**: 変更は要らないが、正本が検査する側にある状態が続く。
   Coreへ同梱したくなったとき、何を正本とし、写しを何と照合するかが決まらない。採用しない。
2. **Core packageへ移す**: 配布物に含まれ、Coreが実行時に読める。しかし検査の基準を検査対象が持つことになり、
   `fixtures/`が`plugins/`を参照することになってADR-049 Decision 6に反する。採用しない。
3. **repository rootに`schemas/`を置く**: 独立した契約directoryとして見つけやすい。しかし詳細設計が
   「Core 1.0の機械契約の正本」と定めており、正本を詳細設計の外へ分けると所有境界が2か所になる。採用しない。

## Notes

- 反映先: [結果・Diagnostic・終了コード §1](../../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#1-所有範囲)、
  [文書・Frontmatter・状態仕様 §2](../../03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#2-frontmatter)、
  [適合fixture仕様 §2](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、[詳細設計README](../../03.詳細設計/README.md)、
  `fixtures/conformance/schemas.py`と各検証器。
- Schemaの内容は変更しない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-24 | 公開結果とFrontmatterのSchemaの正本を`docs/03.詳細設計/schemas/`へ移し、Coreでの扱いと同梱時の規則を確定 | 詳細設計README |
