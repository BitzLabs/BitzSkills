# EARS-AI 共通AST・パーサー仕様 1.0

## 1. 所有者

Parser、AST Schema、Canonical Serializerは `bitz-core` が所有する。各プラグインによるMarkdownの独自再解析は禁止する。

これらはEARS-AI垂直スライス（Phase 1）の成果物であり、`bitz check`の前提となる（[08_実装ロードマップ.md](../../02.設計書/08_実装ロードマップ.md) §3）。

## 2. パイプライン

```text
Markdown
 -> Frontmatter Reader
 -> Normative Line Scanner      (01_Core構文仕様 §3.4)
 -> Core Lexer / Parser / Validator
 -> Profile Resolver / Validators
 -> Canonical AST
 -> Report / Projection / Serializer
```

## 3. AST

```json
{
  "schemaVersion": "1.0",
  "id": "REQ-001:AC-01",
  "documentId": "REQ-001",
  "localId": "AC-01",
  "source": {"path": ".spec/requirements/REQ-001.md", "line": 24, "column": 3},
  "actor": "AuthService",
  "activation": {"kind": "WHEN", "text": "有効な認証情報を受信した場合"},
  "modality": "MUST",
  "operation": {"kind": "THEN", "text": "アクセストークンを1件発行する"},
  "extensions": [],
  "unknownExtensions": [],
  "references": [],
  "untrustedText": true,
  "raw": "..."
}
```

- `text` は §3.3 の正規化（前後空白除去、連続空白の1個化）を適用した後の値を保持する。
- `raw` は正規化前の原文を保持し、Serializerの差分最小化と原文復元に用いる。
- コードスパンは `text` 内でバッククォートを含んだまま保持する。
- `untrustedText` は自由記述本文がツール権限や実行命令ではないことを下流へ伝える。Profileはこの値を解除できない。

## 4. Parser要件

- UTF-8を必須とする。
- 規範箇条書きだけを解析し、フェンス付きコードブロックと引用ブロックの内部を除外する（[01_Core構文仕様.md](01_Core構文仕様.md) §3.4）。これにより仕様書中の記述例が規範文として解釈されない。
- 字句解析はコードスパンを保護し、`\[` `\]` のエスケープを解釈する（同 §3.3）。
- ID形式（2階層固定）、ID重複、タグ順序、必須オペランド、空文字、行末句点を検証する。
- ソース位置を行・列単位で保持する。
- 未知拡張を失わず `unknownExtensions` に保持する。
- Core解析結果をProfileの有無で変化させない。
- ネットワークとAI推論を必要としない決定論的処理とする。同一入力・同一バージョンで必ず同一のASTを返す。

## 5. 正規出力順

1. ID
2. Profile拡張タグ
3. ACTOR
4. 発動条件
5. 規範強度
6. 処理種別と本文

Serializerは意味を書き換えず、フォーマット修正と内容変更を同一パッチへ混在させない。未知拡張を削除せず、正規出力順では既知拡張の後ろへ元の相対順序で配置する。

## 6. 診断

診断は `bitz-core` が所有するDiagnosticスキーマに従う（[01_共通アーキテクチャ.md](../../02.設計書/01_共通アーキテクチャ.md) §6）。Core診断のOWNERセグメントは `EAI` とし、Profile診断は所有拡張のOWNERを用いる（[ADR-003](../../02.設計書/10_決定記録/ADR-003_Diagnostic正本スキーマと診断コード命名規約.md)）。

| コード | 意味 |
|---|---|
| `EAI-CORE-SYNTAX-001` | タグ順序不正 |
| `EAI-CORE-SYNTAX-002` | 必須タグ不足 |
| `EAI-CORE-SYNTAX-003` | 発動条件の複数指定 |
| `EAI-CORE-SYNTAX-004` | 未閉鎖または不正なタグ／未エスケープの `[` |
| `EAI-CORE-SYNTAX-005` | 未閉鎖のコードスパン |
| `EAI-CORE-SYNTAX-006` | 行末句点の欠落 |
| `EAI-CORE-ID-001` | ID形式不正（2階層固定に不適合） |
| `EAI-CORE-ID-002` | ID重複 |
| `EAI-CORE-ID-003` | 削除済みIDの再利用 |
| `EAI-CORE-SEM-001` | オペランド不足 |
| `EAI-CORE-LANG-001` | 正本言語との不一致 |
| `EAI-EXT-UNKNOWN-001` | 未登録拡張 |
| `EAI-EXT-CONFLICT-001` | 拡張競合 |

診断コードは永続識別子とし、再利用と意味変更を禁止する。廃止したコードは予約済みとして本表に残す。
