# EARS-AI言語・Semantic IR仕様 1.0

## 1. 適用範囲

EARS-AI Coreは、全Bitz操作が同じ構造として解析する最小要求言語を定義する。自由記述の意味的正しさ、
SDDフロー、品質指標、DDD modelは定義しない。

Markdownは人間が編集する正本、Semantic IRは決定論的な検査・Context・traceに使う派生表現である。
Semantic IRを正本fileとして保存しない。

## 2. 意味軸

### 2.1 ID

規範文IDは`<document-id>:<local-id>`の2階層固定とする。

```ebnf
document-id  = prefix, "-", 3*DIGIT ;
prefix       = "REQ" / "TECH" / "ADR" / "TASK" ;
local-id     = ALNUM, *( ALNUM / "-" ) ;
statement-id = document-id, ":", local-id ;
```

- 規範文だけにIDを要求する。
- 3階層以上のIDを禁止する。
- 同一workspace内で一意とする。
- 削除したIDを別の意味へ再利用しない。
- 独立して合否判定できる結果は別IDに分ける。

### 2.2 ACTOR

`ACTOR`は応答、生成、制約遵守の責任を負う実行主体である。作成者、承認者、所有teamではない。

### 2.3 発動条件

| tag | 意味 |
|---|---|
| `ALWAYS` | 常時適用 |
| `WHEN` | eventまたは条件成立時 |
| `WHILE` | 状態継続中 |
| `WHERE` | 機能・構成・環境が存在する場合 |
| `IF_ERROR` | 異常または望ましくない条件 |

1文は1つの発動条件を持つ。

### 2.4 規範強度

| tag | 意味 | 未充足 |
|---|---|---|
| `MUST` | 必須 | error |
| `SHOULD` | 推奨 | 理由なしはwarning |
| `MAY` | 任意 | 不適合にしない |

規範強度の省略を禁止する。Coreは強度を保持するが、実装充足はtestまたは人間確認で判断する。

### 2.5 処理種別

| tag | 意味 |
|---|---|
| `THEN` | 観測可能な応答 |
| `GENERATE` | 推論を伴う成果物生成 |
| `CONSTRAINT` | 実装・品質・非機能・禁止制約 |

## 3. 正規構文

```ebnf
statement    = list-marker, SP, "[", statement-id, "]", SP,
               { extension, SP }, actor, SP, activation, SP,
               modality, SP, operation, period ;
list-marker  = "-" ;
extension    = "[", namespace, ":", term, [ "=", value ], "]" ;
actor        = "[ACTOR:", identifier, "]" ;
activation   = "[ALWAYS]"
             | "[WHEN]", SP, text
             | "[WHILE]", SP, text
             | "[WHERE]", SP, text
             | "[IF_ERROR]", SP, text ;
modality     = "[MUST]" | "[SHOULD]" | "[MAY]" ;
operation    = "[THEN]", SP, text
             | "[GENERATE]", SP, text
             | "[CONSTRAINT]", SP, text ;
```

```ebnf
SP           = %x20 ;
UPPER        = %x41-5A ;
LOWER        = %x61-7A ;
DIGIT        = %x30-39 ;
ALPHA        = UPPER / LOWER ;
ALNUM        = ALPHA / DIGIT ;
identifier   = ALPHA, *( ALNUM / "-" / "_" ) ;
namespace    = LOWER, *( LOWER / DIGIT ) ;
term         = UPPER, *( UPPER / DIGIT / "_" ) ;
value        = bare-value / quoted-value ;
bare-value   = 1*( ALNUM / "-" / "_" / "." ) ;
quoted-value = DQUOTE, *( qchar / escaped ), DQUOTE ;
period       = "." / "。" ;
```

extensionはCore 1.0ではopaqueな値として保持する。CoreはProfile Manifest、外部Validator、
Profile固有migrationを読み込まない。
未知名前空間は`EAI-EXT-UNKNOWN-001`／warningとし、Core構文の解析を続ける。

## 4. 字句規則

1. 規範文は1行で完結し、行継続を認めない。
2. code span内の`[`と`]`をtag区切りとして扱わない。
3. code span外の未escape `[`で直前textを終了する。
4. literal `[`はcode spanまたは`\[`で記述する。`\]`、`\\`、``\` ``も受理する。
5. 未閉鎖tagは`EAI-CORE-SYNTAX-004`、未閉鎖code spanは`EAI-CORE-SYNTAX-005`とする。
6. text前後の空白を除去し、内部の連続空白を1個へ正規化する。
7. 行末の`.`または`。`を必須とする。
8. tag順序はID、extension、ACTOR、発動条件、規範強度、処理種別とする。

同じ位置で複数一致する場合はcode span、既知escape、tag開始、通常文字の順で確定する。

## 5. 規範行候補

候補抽出と完全構文検証を分離する。

1. fenced code blockと引用block内部を候補にしない。
2. 先頭空白を除いた行が`- [`で始まり、最初の角括弧が次のいずれかなら候補とする。
   - 文書IDらしいtoken
   - Core tag
   - `[a-z][a-z0-9]*:`のnamespace形式
3. GFM checkboxの`- [ ]`、`- [x]`、`- [X]`を除外する。
4. Scannerはstatement IDの妥当性を要求せず、候補をLexer／Parser／Validatorへ渡す。
5. 候補でない行へIDと規範強度を要求しない。

これにより、桁数不足、未知prefix、3階層、ID欠落を通常本文として見逃さない。

## 6. Semantic IR

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
  "untrustedText": true,
  "raw": "..."
}
```

Semantic IRはID、source、actor、activation、modality、operation、extensionを保持する。
Lexer token、Markdown装飾、区切り文字の具象nodeは公開Schemaに含めない。

- `text`は正規化後の値を保持する。
- `raw`は診断と原文参照のため保持する。
- `untrustedText`は常にtrueで、extensionが解除できない。
- JSONをCoreとadapter間の機械契約とする。
- `semanticHash`と`fileHash`を公開fieldにしない。

## 7. ParserとSerializer

- UTF-8を必須とする。
- 候補Scannerを先に適用する。
- ID、重複、tag順序、必須operand、空文字、句点を検証する。
- source位置を行・列単位で保持する。
- opaque extensionを失わない。
- extensionの有無でCore解析結果を変えない。
- networkとAI推論を使わない。
- 同一入力・同一versionから同一Semantic IRを返す。

Serializerは正規tag順へ整形できるが意味を変更しない。format変更と内容変更を同一patchへ混ぜず、
opaque extensionを削除しない。Core 1.0は公開`bitz fmt`を提供しない。

## 8. 原子性と文体

- 独立して失敗、変更、検証できる結果は別IDへ分割する。
- 1文で複数actorへ義務を課さない。
- 型、関数、状態、code値はcode spanにする。
- 数値条件は単位、比較演算、許容誤差を明示する。
- 「適切に」「必要に応じて」「高速に」など判定不能な表現を避ける。

## 9. Diagnostic

| code | severity | `resultStatus` | 条件 |
|---|---|---|---|
| `EAI-CORE-SYNTAX-001` | error／draftはwarning | `failed`／`passed_with_warnings` | tag順序不正 |
| `EAI-CORE-SYNTAX-002` | error／draftはwarning | `failed`／`passed_with_warnings` | 必須tag不足 |
| `EAI-CORE-SYNTAX-003` | error／draftはwarning | `failed`／`passed_with_warnings` | 発動条件複数 |
| `EAI-CORE-SYNTAX-004` | error／draftはwarning | `failed`／`passed_with_warnings` | 不正・未閉鎖tag |
| `EAI-CORE-SYNTAX-005` | error／draftはwarning | `failed`／`passed_with_warnings` | 未閉鎖code span |
| `EAI-CORE-SYNTAX-006` | error／draftはwarning | `failed`／`passed_with_warnings` | 句点欠落 |
| `EAI-CORE-ID-001` | error | `failed` | ID形式不正 |
| `EAI-CORE-ID-002` | error | `failed` | 規範文ID重複 |
| `EAI-CORE-SEM-001` | error／draftはwarning | `failed`／`passed_with_warnings` | operand不足 |
| `EAI-CORE-LANG-001` | warning | `passed_with_warnings` | 正本言語との不一致 |
| `EAI-EXT-UNKNOWN-001` | warning | `passed_with_warnings` | opaque extension |

ID系は索引を壊すためdraftでもerrorとする。

## 10. 言語

1 workspace内の規範文を単一言語にすることを推奨し、正本言語は`bitz.yaml.language`で指定する。
自動翻訳同期と意味的同一性判定はCore 1.0の対象外とする。
