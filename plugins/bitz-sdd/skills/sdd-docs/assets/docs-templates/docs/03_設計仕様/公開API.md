---
id: DOC-design-public-api
title: Public API & Compatibility
status: active
version: 0.1.0
changeImpact: low
project_type: library        # このテンプレは library 専用。app では削除。
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null
---

<!--
  library の最重要文書。「利用者に対する恒久的な契約」を定義する。
  ここでの version（frontmatter）は文書の版であり、パッケージの SemVer とは別。
  パッケージの互換性ルールは本文の「互換性ポリシー」で規定する。
-->

# Public API & Compatibility

## 公開面 (Public Surface)

<!-- 何が公開契約で、何が非契約かを列挙。ここに無いものは互換保証しない。 -->

| 契約単位 | 安定度 | 備考 |
|---|---|---|
| <型/関数/モジュール名> | `stable` | 破壊的変更は major のみ |
| <型/関数名> | `experimental` | minor で変わり得る。要 opt-in |
| <型/関数名> | `internal` | 契約外。予告なく変更 |

安定度の意味:
- **stable** … SemVer の完全対象。破壊は major bump でのみ。
- **experimental** … 変更あり得る。feature フラグや `preview` 名前空間で隔離。
- **internal** … 公開シンボルでも契約外（言語ごとに下記で隠蔽/明示）。

## 互換性ポリシー (SemVer)

- **MAJOR**: 既存の stable 契約を壊す変更（シグネチャ削除・意味変更）。
- **MINOR**: 後方互換な追加（新 API・新オーバーロード・新 feature）。
- **PATCH**: 契約に影響しない修正。

> 原則: **追加は additive に**。既存シンボルの意味は変えず、新規追加で拡張する。

## 非推奨ポリシー (Deprecation)

1. 代替を用意してから非推奨化する。
2. 最低 <N> 個の minor を非推奨期間として維持。
3. 削除は次の major でのみ。CHANGELOG と移行ガイドを添える。

## 言語別の具体

### C# (NuGet)
- **バイナリ互換**: public シグネチャの削除・変更は破壊的。`internal` + `InternalsVisibleTo` で契約外を隔離。
- **対象フレームワーク (TFM)**: サポートする `net8.0` 等を明記。TFM 追加は minor、削除は major。
- **非推奨**: `[Obsolete("理由。代替: X", error: false)]` → 期間後 `error: true` → major で削除。
- **null 許容**: NRT 注釈 (`?`) の変更は契約の一部として扱う。
- **注意**: default 引数値の変更、`struct` のレイアウト変更、public フィールド→プロパティ化は破壊的。

### TypeScript (npm / Web)
- **公開面**: `package.json` の `exports` マップが契約。サブパスの削除は破壊的。
- **型契約**: 公開 `.d.ts` の型は API の一部。型の狭める変更は破壊的（広げるのは概ね互換）。
- **非推奨**: `@deprecated` JSDoc + 型は残す → 次 major で削除。
- **デュアル環境**: ESM/CJS、ブラウザ/Node の対応マトリクスを明記。`sideEffects` 宣言を維持。
- **注意**: `tsconfig` の `strict` 前提や最低 TS バージョンも契約。引き上げは破壊的扱い。

### Rust (crates.io)
- **SemVer**: `pub` items が契約。[cargo SemVer 互換ガイド] に従う。
- **MSRV**: 最低サポート Rust バージョンを明記。引き上げは（方針により）minor か major。CI で固定。
- **feature 加法性**: feature は additive に保つ（有効化で既存が壊れない）。`default` feature の削除は破壊的。
- **非推奨**: `#[deprecated(since = "x.y.z", note = "代替: ...")]` → 次 major で削除。
- **edition**: edition 変更は利用者に影響し得るため方針を明記。
- **注意**: 公開 struct へのフィールド追加は破壊的になり得る（`#[non_exhaustive]` で予防）。trait への必須メソッド追加も破壊的。

## 移行ガイドの置き場

- 破壊的変更 (major) ごとに CHANGELOG に移行手順を記載。
- 大きな移行は `06-reference/migration-<version>.md` に切り出す（成長フェーズ）。

---
### Revision History
| version | date | change | impact |
|---|---|---|---|
| 0.1.0 | 2026-07-07 | 初版 | — |
