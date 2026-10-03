---
id: ADR-050
title: 契約スキーマの正本を詳細設計へ置く
status: accepted
relations:
  requires:
    - ADR-045
    - ADR-049
  related:
    - ADR-046
---

# ADR-050 契約スキーマの正本を詳細設計へ置く

## Context

公開するJSONの結果のスキーマ（`result.schema.json`）とフロントマターのスキーマ（`frontmatter.schema.json`）は、
[結果・診断・終了コード §1](../../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#1-本書の範囲)と
[文書・フロントマター・状態仕様 §2](../../03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#2-フロントマター)が
機械可読な正本として参照する契約である。これらは`fixtures/conformance/`に置かれていた。
この配置には次の問題がある。

1. 契約の正本が、それを検査する側のディレクトリにある。仕様から試験への依存の向きが逆になる。
2. [ADR-049](ADR-049_Coreのsource配置と試験の構成を確定する.md)の`Decision`の6番目の項目により、`plugins/bitz-core`は`fixtures/`を参照しない。
   フロントマター仕様は「Coreは同Schemaの定義を選んで検証する」としていたが、Coreは正本を読めない。
3. [ADR-045](ADR-045_実行環境と配布物の確定.md)の`Decision`の3番目の項目により、Coreのランタイムの依存は標準ライブラリとYAMLライブラリ1つに限られ、
   JSON Schemaの検証プログラムを使えない。スキーマファイルを読めたとしても、そのまま評価する手段がない。

正本をCoreのパッケージへ移すと、Gate Bで検査される側が検査の基準を持つことになる。Coreの変更がスキーマを緩めても
合格し得る。[ADR-046](ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)がパッケージの検査を
`bitz.compat`へ含める案を自己申告として採らなかったのと同じ構造である。

## Decision

1. **正本の配置**: `result.schema.json`と`frontmatter.schema.json`の正本を`docs/03.詳細設計/schemas/`へ置く。
   [詳細設計](../../03.詳細設計/README.md)がCore 1.0の機械契約の正本であることに合わせる。
2. **fixture形式のスキーマ**: fixture自身の形式を定める`manifest.schema.json`と`side-effects.schema.json`は、
   `fixtures/conformance/`に残す。
3. **参照の向き**: `fixtures/`と`tests/`は契約のスキーマを`docs/03.詳細設計/schemas/`から読み、写しを持たない。
   Gate A・Bで期待値とCoreの出力を検査する基準は、この正本だけとする。
4. **Coreでの扱い**: Coreは契約のスキーマと同じ判定を行う。スキーマファイルを実行のときに読むこと、JSON Schemaの検証プログラムを
   使うことは要求しない。フロントマター仕様 §2の「定義を選んで検証する」はこの意味とする。
5. **Coreへの同梱**: 将来Coreのパッケージへスキーマを同梱する場合は、プラグインのディレクトリ内に写しを置き、
   写しが正本とバイト単位で一致することを`fixtures/`または`tests/`の側で検査する。写しを正本にしない。

## Consequences

- 詳細設計の本文と、その機械可読な正本が同じディレクトリにそろう。表・例とスキーマの同時修正を確認しやすくなる。
- fixtureの検証プログラムは、スキーマの場所を`fixtures/conformance/schemas.py`の`schema_path`で解決する。
  契約のスキーマは常に正本から読み、fixture形式のスキーマはfixtureのルートから読む。
- Coreは、フロントマターと結果の外形の判定を標準ライブラリで実装する。判定と正本の一致は、適合fixtureと
  Gate Bで確認する。
- 配置の変更でGate Aの認定対象の内容が変わるため、`certify_gate_a.py`で再認定する。
- `docs/`はMarkdownの設計資料だけでなく、機械可読なスキーマも持つ。

## Alternatives

1. **`fixtures/conformance/`に残す**: 変更は要らないが、正本が検査する側にある状態が続く。
   Coreへ同梱したくなったとき、何を正本とし、写しを何と照合するかが決まらない。採用しない。
2. **Coreのパッケージへ移す**: 配布物に含まれ、Coreが実行のときに読める。しかし検査の基準を検査対象が持つことになり、
   `fixtures/`が`plugins/`を参照することになってADR-049の`Decision`の6番目の項目に反する。採用しない。
3. **リポジトリのルートに`schemas/`を置く**: 独立した契約のディレクトリとして見つけやすい。しかし詳細設計が
   「Core 1.0の機械契約の正本」と定めており、正本を詳細設計の外へ分けると正本の所有が2か所に分かれる。採用しない。

## Notes

- 反映先: [結果・診断・終了コード §1](../../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#1-本書の範囲)、
  [文書・フロントマター・状態仕様 §2](../../03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#2-フロントマター)、
  [適合fixture仕様 §2](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、[Core 1.0詳細設計](../../03.詳細設計/README.md)、
  `fixtures/conformance/schemas.py`と各検証プログラム。
- スキーマの内容は変更しない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-24 | 公開結果とFrontmatterのSchemaの正本を`docs/03.詳細設計/schemas/`へ移し、Coreでの扱いと同梱時の規則を確定 | 詳細設計README |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
