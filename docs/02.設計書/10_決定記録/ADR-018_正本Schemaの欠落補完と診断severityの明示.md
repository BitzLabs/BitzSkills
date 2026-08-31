---
id: ADR-018
title: 正本Schemaの欠落補完と診断severityの明示
status: accepted
relations:
  related:
    - ADR-009
    - ADR-011
    - ADR-014
    - ADR-016
---

# ADR-018 正本Schemaの欠落補完と診断severityの明示

## Context

ADR-009以降、Profile、モノレポ連合、Revision History、Agent Plugins配布を段階的に追加した。
その結果、上位文書が前提とする設定キー・Frontmatter項目・実行パラメータ・診断severityが、
下位の正本Schemaに定義されないまま残った箇所が5件生じた。

いずれも文書間で相反する2つの規則があるのではなく、**片方に定義が存在しない**。
このため実装者は仕様から動作を決定できず、同一入力から同一Diagnosticを得るという
適合性試験（[03_CLI統合設計](../03_CLI統合設計.md) §8）を成立させられない。

| # | 欠落 | 参照側 | 正本側 |
|---:|---|---|---|
| 1 | `profiles`設定キー | 拡張プロファイル仕様、doctor仕様、モノレポ仕様 | `bitz.yaml`仕様にキーなし |
| 2 | `verify`の実行位置 | `bitz.yaml`仕様が`cwd`を定義 | 参照・トレース・検証仕様が実行位置をworkspaceルートへ固定 |
| 3 | Frontmatterの責任者項目 | Core構文仕様が`owners`を指示 | Frontmatter共通仕様に`owners`なし |
| 4 | `EAI-*`のseverity | 共通アーキテクチャが終了コードをseverityから決定 | AST・パーサー仕様にseverity列なし |
| 5 | Profile間依存 | 拡張プロファイル仕様が`dependencies`を許可 | ADR-016が拡張間の必須依存を禁止 |

## Decision

1. `.spec/bitz.yaml`へ`profiles`を予約キーとして追加する。Core 1.0は型だけを検査し、
   未知キー警告を出さず、互換性判定とContext Digestへ使用しない。
   `doctor`とモノレポ全体検査のProfile互換性判定は、Profileの正式実装まで行わない。
2. `bitz verify`は解決した`verify.commands[].cwd`で実行する。`cwd`未指定のコマンドだけ、
   テストを所有するワークスペースルートを実行位置とする。テストパスの重複排除は
   `argv`と`cwd`の組を単位とする。
3. 作成者・承認者・説明責任者はCoreの共通Frontmatter項目にせず、`x-owners`などの
   プロジェクト拡張で表す。EARS-AI規格本文の`owners`の記述を`x-`拡張へ改める。
4. `EAI-*`診断へseverityを定義する。構文・意味系は`error`とし、所有文書が`draft`の場合だけ
   `warning`へ降格する。ID系3コードは`status`にかかわらず`error`とする。
   `EAI-CORE-LANG-001`と`EAI-EXT-UNKNOWN-001`は`warning`とする。
5. Profile Manifestから`dependencies`を削除し、Profile間の依存宣言を無条件に禁止する。

## Consequences

- Profile未実装のままでも、`profiles`宣言が警告を生まずに前方互換の枠として機能する。
- `cwd`を持つ検証コマンドが仕様どおり動作し、結果JSONの`cwd`と実行位置が一致する。
- `ACTOR`と責任者の分離が、規格本文と正本Schemaで同じキー名を指すようになる。
- 全`EAI-*`コードがseverityを持ち、終了コードが文書から決定できる。
- Profile間の共有語彙が必要になった場合、Coreの公開語彙への昇格が唯一の経路になる。
- マーケットプレイスCIへ、Profile Manifestの`dependencies`不在検査が加わる。
- 結果JSONの`commands[].argv`と`commands[].tests`は、`cwd`が`"."`でない場合に一致しない。
  レポートを読む側はこの差を前提にする。

## Alternatives

1. **`profiles`の参照を4文書から削除する**: Profile正式実装時に同じキーを再導入することになり、
   その時点で警告を受けていた既存設定との整合を別途取る必要が生じる。
2. **Frontmatterの共通項目へ`owners`を追加する**:
   [02_specディレクトリ仕様](../02_specディレクトリ仕様.md)の「owner、日時などは必要なプロジェクトだけが
   拡張する」と、SPECファイル規定 原則3の両方を変更する必要があり、影響範囲が逆側の修正より大きい。
3. **severityを実装裁量に委ねる**: 同一fixtureから同一Diagnosticを得る適合性試験が成立しない。
4. **Profile依存をManifestで解決する**: Agent Plugins 1.0に依存解決機構がなく、
   単体導入時に未解決依存を検出できない（ADR-016）。

## Notes

本ADRは[04.提案資料/03_設計書・詳細設計レビューと改訂提案](../../04.提案資料/03_設計書・詳細設計レビューと改訂提案.md)
§2のP1 5件に対する裁定であり、同書 附録Aの差分を適用して確定した。
本ADR作成時点では同書のP2・P3は未裁定であり、本ADRの対象外とした。その後、P2はADR-019、
決定記録の自己適合性はADR-020、P3は提案資料READMEの裁定として反映済みである。

Decision 2のテストパス重複排除単位`(argv, cwd)`は、[ADR-030](ADR-030_verify実行bindingの正規識別子と重複排除単位の統一.md)が
`(workspaceId, 正規化argv template, 正規化cwd)`へ置き換えた。本ADRの他のDecisionは有効である。

関連文書: [EARS-AI規格/01](../../03.詳細設計/01_EARS-AI規格/01_Core構文仕様.md), [EARS-AI規格/02](../../03.詳細設計/01_EARS-AI規格/02_拡張プロファイル仕様.md), [EARS-AI規格/06](../../03.詳細設計/01_EARS-AI規格/06_AST・パーサー仕様.md), [SPECファイル規定/02](../../03.詳細設計/02_SPECファイル規定/02_bitz.yaml仕様.md), [SPECファイル規定/03](../../03.詳細設計/02_SPECファイル規定/03_Frontmatter共通仕様.md), [SPECファイル規定/06](../../03.詳細設計/02_SPECファイル規定/06_参照・トレース・検証仕様.md), [SPECファイル規定/11](../../03.詳細設計/02_SPECファイル規定/11_doctor仕様.md), [SPECファイル規定/12](../../03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | 初版を作成 | — |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
| 2026-08-31 | Decision 2の重複排除単位が`ADR-030`へ置換されたことを注記 | `ADR-030` |
