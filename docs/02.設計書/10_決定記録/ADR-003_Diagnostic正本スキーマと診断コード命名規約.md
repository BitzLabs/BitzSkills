---
id: ADR-003
title: Diagnostic正本スキーマと診断コード命名規約
status: superseded
---

# ADR-003 Diagnostic正本スキーマと診断コード命名規約

## Context

診断オブジェクトが3箇所で別々に定義され、`summary` と `message`、`specRefs` と `statementId` が重複していた。共通結果形式の `diagnostics` は要素型が未定義であり、この状態ではJSON Schemaを確定できない。

診断コードも `BQ-TRACE-001`、`EAI-CORE-SYNTAX-001`、`EAI-DDD-AGG-001` の3系統が無規約に併存し、`EAI-DDD-*` はCore所有かProfile所有かが読み取れなかった。

## Decision

### Diagnosticスキーマ

`bitz-env` が Diagnostic の正本スキーマを単独で所有する。全プラグインとProfile Validatorはこの1つの型を返す。

- 人間向け1行要約のフィールド名は `summary` に統一する（`message` は廃止）。
- 仕様参照は `specRefs`（配列）に統一する。単一のstatementを指す場合も配列1要素とする。
- プラグイン固有の追加情報は `extensions.<plugin-id>` へ格納し、正本スキーマへ新フィールドを追加しない。
- 必須フィールドは `code`、`severity`、`summary`、`source` とし、他は任意とする。

### 診断コード命名規約

`<OWNER>-<CATEGORY>-<NNN>` の3セグメント固定とする。

- `OWNER` は所有プラグインを表す。`EAI` はEARS-AI Coreのみが使用する。
- Profileの診断は所有プラグインのOWNERを使用する。`EAI-DDD-*` は誤りであり、`BD-AGG-001` のように `bitz-ddd` 自身のOWNERを用いる。
- コードは永続識別子とし、再利用と意味変更を禁止する。廃止時はコードを予約済みとして残す。

### 理由

- 診断は全プラグイン境界を通過する唯一の共通データであり、複数定義は統合試験で必ず破綻する。
- OWNERセグメントを所有プラグインに一致させることで、診断からルール所有者を機械的に解決できる。

## Consequences

- OWNER一覧の管理は `bitz-env` が行い、プラグイン登録時に一意性を検証する。
- 既存記述の `BQ-TRACE-001` は規約に適合するため変更しない。`EAI-DDD-AGG-001` は `BD-AGG-001` へ改める。

## Alternatives

1. **プラグインごとに独自診断型を許し、集約時に変換**: 却下。変換層が全プラグイン数だけ必要になり、フィールド欠落が検出できない。
2. **`EAI-` を全EARS-AI関連診断の接頭辞とする**: 却下。Profile診断の所有者が判別できず、Coreの互換性保証範囲が曖昧になる。

## Notes

関連文書: [01_共通アーキテクチャ.md](../01_共通アーキテクチャ.md), [05_QA品質保証設計.md](../05_QA品質保証設計.md), [EARS-AI規格/02_拡張プロファイル仕様.md](../../03.詳細設計/01_EARS-AI規格/02_拡張プロファイル仕様.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-25 | 初版を作成 | — |
| 2026-08-25 | ADR-011がDiagnostic所有者とコード形式を改訂 | `ADR-011` |
| 2026-08-25 | ADR-009により置換 | `ADR-009` |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
