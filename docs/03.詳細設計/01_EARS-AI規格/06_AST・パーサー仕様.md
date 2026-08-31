# EARS-AI 共通Semantic IR（AST）・パーサー仕様 1.0

## 1. 所有者

Parser、Semantic IR Schema、Canonical Serializerは `bitz-core` が所有する。各プラグインによるMarkdownの独自再解析は禁止する。

既存の公開名称との互換性のため本規格では `AST` という語を残すが、その実体は字句や括弧を全ノードとして
保持する具象構文木ではなく、EARS-AI規範文の意味軸だけを正規化した **Semantic IR** である。
LLMへ構文解析を委ねず、Core、Profile、Context Resolutionが同じ意味表現を共有するために生成する。

これらはEARS-AI垂直スライス（Phase 1）の成果物であり、`bitz check`の前提となる（[08_実装ロードマップ.md](../../02.設計書/08_実装ロードマップ.md) §3）。

## 2. パイプライン

```text
Markdown
 -> Frontmatter Reader
 -> Excluded Region Reader      (コードブロック・引用)
 -> Normative Candidate Scanner (01_Core構文仕様 §3.4)
 -> Core Lexer / Parser / Validator
 -> Profile Resolver / Validators
 -> Canonical Semantic IR (AST互換名)
 -> Validator / Context Projection / Serializer
```

Markdownは人間が編集する正本、Semantic IRは決定論的な検査・依存解決・投影のための派生表現、
Projectionは目的別にLLMへ渡す提示表現とする。Semantic IRやProjectionを正本として保存しない。

## 3. Semantic IR

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

### 3.1 表現境界

- Semantic IRは、ID、出典、主体、発動条件、規範強度、処理、拡張、参照を保持する。
- Lexer token、区切り文字、Markdown装飾の構文ノードは公開Schemaへ含めない。必要ならParser内部だけで保持する。
- `raw`と`source`は診断、差分最小化、原文参照に使う付帯情報であり、LLM向けProjectionへの常時収録を要求しない。
- Context Digestが使うSemantic IRのCanonical表現からは、`raw`、絶対パス、行・列を除外し、
  正規化済み意味フィールドと拡張を含める。現行契約の変更検出は`semanticHash`、履歴を含む
  ファイル全体の変更検出は`fileHash`が担う。
- JSONはCoreとアダプター間の機械契約とする。LLM向けMarkdownはSemantic IRから生成できる表示であり、
  JSONと独立した意味解釈を追加してはならない。

この境界により、決定論的な検査と句単位トレースには構造化表現を使いながら、LLMへ原文とJSONを
無条件に二重投入することを避ける。Context Bundleでの具体的な提示規則は
[Context Resolution仕様](../02_SPECファイル規定/10_Context%20Resolution仕様.md)に従う。

## 4. Parser要件

- UTF-8を必須とする。
- フェンス付きコードブロックと引用ブロックを先に除外し、[01_Core構文仕様.md](01_Core構文仕様.md) §3.4の
  広い候補規則で規範行候補を抽出する。候補抽出時に正しい`statement-id`への一致を要求しない。
- 通常のGFM checkboxを候補から除外する。
- 字句解析はコードスパンを保護し、`\[` `\]` のエスケープを解釈する（同 §3.3）。
- ID形式（2階層固定）、ID重複、タグ順序、必須オペランド、空文字、行末句点を検証する。
- ソース位置を行・列単位で保持する。
- 未知拡張を失わず `unknownExtensions` に保持する。
- Core解析結果をProfileの有無で変化させない。
- ネットワークとAI推論を必要としない決定論的処理とする。同一入力・同一バージョンで必ず同一のSemantic IRを返す。

適合性fixtureには、3桁未満ID、未知prefix、3階層ID、ID欠落、通常checkbox、コードブロック、引用ブロックを
それぞれ1件以上含める。不正IDの候補行が通常本文として無視されないことを検証する。

## 5. 正規出力順

1. ID
2. Profile拡張タグ
3. ACTOR
4. 発動条件
5. 規範強度
6. 処理種別と本文

Serializerは意味を書き換えず、フォーマット修正と内容変更を同一パッチへ混在させない。未知拡張を削除せず、正規出力順では既知拡張の後ろへ元の相対順序で配置する。

## 6. 診断

診断は`bitz-core`が所有するDiagnosticスキーマに従う（[01_共通アーキテクチャ.md](../../02.設計書/01_共通アーキテクチャ.md) §6）。Core診断のOWNERセグメントは`EAI`とし、Profile診断は所有拡張のOWNERを用いる（[ADR-011](../../02.設計書/10_決定記録/ADR-011_Diagnostic所有者とコード命名規約.md)）。

| コード | severity | `resultStatus` | 意味 |
|---|---|---|---|
| `EAI-CORE-SYNTAX-001` | error（`draft`ではwarning） | `failed`（降格時は`passed_with_warnings`） | タグ順序不正 |
| `EAI-CORE-SYNTAX-002` | error（`draft`ではwarning） | `failed`（降格時は`passed_with_warnings`） | 必須タグ不足 |
| `EAI-CORE-SYNTAX-003` | error（`draft`ではwarning） | `failed`（降格時は`passed_with_warnings`） | 発動条件の複数指定 |
| `EAI-CORE-SYNTAX-004` | error（`draft`ではwarning） | `failed`（降格時は`passed_with_warnings`） | 未閉鎖または不正なタグ／未エスケープの `[` |
| `EAI-CORE-SYNTAX-005` | error（`draft`ではwarning） | `failed`（降格時は`passed_with_warnings`） | 未閉鎖のコードスパン |
| `EAI-CORE-SYNTAX-006` | error（`draft`ではwarning） | `failed`（降格時は`passed_with_warnings`） | 行末句点の欠落 |
| `EAI-CORE-ID-001` | error | `failed` | ID形式不正（2階層固定に不適合） |
| `EAI-CORE-ID-002` | error | `failed` | ID重複 |
| `EAI-CORE-ID-003` | error | `failed` | Git基準版に存在し現在は削除されているIDの再利用。基準版がない場合は実施不能 |
| `EAI-CORE-SEM-001` | error（`draft`ではwarning） | `failed`（降格時は`passed_with_warnings`） | オペランド不足 |
| `EAI-CORE-LANG-001` | warning | `passed_with_warnings` | 正本言語との不一致 |
| `EAI-EXT-UNKNOWN-001` | warning | `passed_with_warnings` | 未登録拡張 |
| `EAI-EXT-CONFLICT-001` | error | `failed` | 拡張競合 |

`draft`での降格は、所有文書の`status`が`draft`である場合だけ適用する。ID系3コードは、
`status`にかかわらず`error`とする。IDは文書を越えた索引と参照解決の基礎であり、
`draft`の不正IDが他文書の参照検査を壊すためである。

severityと結果statusは[共通アーキテクチャ](../../02.設計書/01_共通アーキテクチャ.md) §5〜6および
[ADR-021](../../02.設計書/10_決定記録/ADR-021_Diagnostic-severity・操作status・source-Schemaの分離.md)に従う。
EARS-AI Validatorでは本表のerrorを成果物不適合の`failed`へ対応付け、warningだけなら
`passed_with_warnings`とする。この対応をdoctorやContextの前提不足へ一般化しない。
Profile診断のseverityは各Profile文書が同じ形式で定義する。

診断コードは永続識別子とし、再利用と意味変更を禁止する。廃止したコードは予約済みとして本表に残す。
