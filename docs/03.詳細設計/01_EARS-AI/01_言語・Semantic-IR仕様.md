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
document-id  = prefix, "-", digit, digit, digit, { digit } ;
prefix       = "REQ" | "TECH" | "ADR" | "TASK" ;
local-id     = alnum, { alnum | "-" } ;
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
| `SHOULD` | 推奨 | `[REASON]`なしは`EAI-CORE-SHOULD-001`／warning |
| `MAY` | 任意 | 不適合にしない |

規範強度の省略を禁止する。`SHOULD`の理由は`[SHOULD] [REASON] <text>`で明示する。
理由なしの`[SHOULD]`もparseしてSemantic IRの`reason`をnullにするが、warningを返す。
`MUST`と`MAY`へ`[REASON]`を付けてはならない。Coreは強度と理由を保持するが、実装充足はtestまたは人間確認で判断する。

### 2.5 処理種別

| tag | 意味 |
|---|---|
| `THEN` | 観測可能な応答 |
| `GENERATE` | 推論を伴う成果物生成 |
| `CONSTRAINT` | 実装・品質・非機能・禁止制約 |

## 3. 正規構文

本節はISO/IEC 14977相当のEBNFだけを使用する。`,`は連接、`|`は選択、`[ ... ]`は省略可能、
`{ ... }`は0回以上の繰返し、`;`は規則終端、引用符内はterminalを表す。ABNFの`%x`、`n*element`、`/`を使用しない。
入力は妥当なUTF-8から復号したUnicode scalar value列とし、文法は1 code point単位で評価する。

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
modality     = "[MUST]" | should-modality | "[MAY]" ;
should-modality = "[SHOULD]", [ SP, reason ] ;
reason       = "[REASON]", SP, text ;
operation    = "[THEN]", SP, text
             | "[GENERATE]", SP, text
             | "[CONSTRAINT]", SP, text ;
text         = text-atom, { text-atom } ;
text-atom    = plain-char | escaped | code-span ;
escaped      = "\\", ( "[" | "]" | "\\" | "`" | DQUOTE ) ;
code-span    = backtick-run, { code-char }, backtick-run ;
backtick-run = "`", { "`" } ;
identifier   = alpha, { alnum | "-" | "_" } ;
namespace    = lower, { lower | digit } ;
term         = upper, { upper | digit | "_" } ;
value        = bare-value | quoted-value ;
bare-value   = bare-char, { bare-char } ;
bare-char    = alnum | "-" | "_" | "." ;
quoted-value = DQUOTE, { qchar | escaped }, DQUOTE ;
period       = "." | "。" ;
SP           = " " ;
DQUOTE       = '"' ;
upper        = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J"
             | "K" | "L" | "M" | "N" | "O" | "P" | "Q" | "R" | "S" | "T"
             | "U" | "V" | "W" | "X" | "Y" | "Z" ;
lower        = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j"
             | "k" | "l" | "m" | "n" | "o" | "p" | "q" | "r" | "s" | "t"
             | "u" | "v" | "w" | "x" | "y" | "z" ;
digit        = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
alpha        = upper | lower ;
alnum        = alpha | digit ;
```

`plain-char`は`[`、`\\`、backtick、CR、LF以外のUnicode scalar valueである。`]`は単独の通常文字として許可する。
`qchar`はDQUOTE、`\\`、CR、LF以外、`code-char`はCR、LF以外のUnicode scalar valueである。
これら3つは否定集合であるため上の有限な生成規則とは分けて定義する。

`backtick-run`は連続するbacktickの極大列として読み取る。開始runと同じ個数のbacktickからなる最初のrunだけを
終了delimiterとする。
異なる長さのrunは`code-char`として保持する。code span内ではescapeとtagを解釈しない。
`text`の終了位置は次に現れる未escapeの既知tag開始で決める。operationの`text`では、code span外にある行末直前の
最後の`.`または`。`を`period`とし、それ以前を`text`とする。空の`text`は許可しない。

quoted value内の`escaped`はescape後の1 code pointを値へ保持する。text内も同じ解除を行う。
未知escape、未閉鎖quoted value、開始runと同じ終了runがないcode span、未閉鎖tagを受理しない。

extensionはCore 1.0ではopaqueな値として保持する。CoreはProfile Manifest、外部Validator、
Profile固有migrationを読み込まない。
未知名前空間は`EAI-EXT-UNKNOWN-001`／warningとし、Core構文の解析を続ける。

## 4. 字句規則

1. 規範文は1行で完結し、行継続を認めない。
2. code span内の`[`と`]`をtag区切りとして扱わない。
3. code span外の未escape `[`で直前textを終了する。
4. literal `[`はcode spanまたは`\[`で記述する。`\]`、`\\`、``\` ``も受理する。
5. 未閉鎖tagは`EAI-CORE-SYNTAX-004`、未閉鎖code spanは`EAI-CORE-SYNTAX-005`とする。
6. text前後のSPとTABを除去し、内部の連続SP／TABを1個のSPへ正規化する。その他のUnicode空白文字は保持する。
7. 行末の`.`または`。`を必須とする。
8. tag順序はID、extension、ACTOR、発動条件、規範強度、処理種別とする。

Lexerは行を左から右へ1回走査し、`TEXT`、`CODE_SPAN`、`TAG`、`SP`、`PERIOD` tokenを返す。
同じ位置で複数一致する場合はcode span、既知escape、tag開始、period、通常文字の順で確定する。
`PERIOD`にするのはcode span外にある行末の`.`または`。`だけであり、それ以外の句点は`TEXT`へ含める。
quoted value内ではDQUOTE、既知escape、qcharの順とする。tokenの開始・終了offsetとDiagnosticのline／columnは
Unicode code point単位の1始まりとし、TAB、結合文字、全角文字も各1 columnと数える。改行code pointはtokenに含めない。

同じraw原因から複数のsyntax候補が生じる場合は、未閉鎖code span、未閉鎖／不正tag、ID形式、tag順序、
必須tag不足、発動条件複数、句点欠落、operand不足の順でprimaryを1件だけ返す。別位置の独立原因はそれぞれ返す。
[Diagnostic registry](../00_共通契約/05_Diagnostic-registry.md)のpriorityはこの順序と一致させる。

## 5. 規範行候補

候補抽出と完全構文検証を分離する。

ScannerはLFへ改行を正規化した後、次の状態機械を文書先頭から行単位で実行する。

```text
state = NORMAL
for each line:
  indent = 行頭の連続SP数
  if state == FENCE:
    if indent <= 3 and 行がopeningと同じ文字のrunで始まり、
       run長 >= opening run長かつ残りがSPだけ: state = NORMAL
    continue
  if indent <= 3 and 行が3個以上の連続backtickまたはtildeで始まる:
    state = FENCE(opening文字, run長)
    continue
  if indent >= 4: continue
  cursor = indent
  if cursor < line.length and line[cursor] == ">": continue
  if lineがcursor位置から正確に"- ["で始まらない: continue
  token = 最初の"["の直後から最初の"]"または行末まで
  if tokenが" "、"x"、"X"のいずれか: continue
  if IsCandidateToken(token): emit candidate(line, cursor + 3)
```

opening fenceのrun後にinfo stringがあってもopeningとする。closing fenceにinfo stringは許可しない。
引用は先頭0〜3 SPの直後が`>`である行を指し、引用内のlistを候補にしない。TABをindentまたはSPとして扱わない。
`cursor + 3`は最初の`[`の1始まりcolumnである。

`IsCandidateToken`は次のいずれかを満たす場合だけtrueとする。判定はASCIIかつcase-sensitiveで、tokenの妥当性を要求しない。

1. `REQ`、`TECH`、`ADR`、`TASK`のいずれかで始まる。
2. ASCII uppercaseで始まり、`-`または`:`を1個以上含む。未知prefix、桁不足、3階層を候補に残すための規則である。
3. `ACTOR`、`ALWAYS`、`WHEN`、`WHILE`、`WHERE`、`IF_ERROR`、`MUST`、`SHOULD`、`MAY`、
   `REASON`、`THEN`、`GENERATE`、`CONSTRAINT`のいずれかで始まる。ID欠落と不正Core tagを候補に残す。
4. `lower, { lower | digit }, ":"`に一致するprefixを持つ。extensionから始まるID欠落を候補に残す。

Scannerは角括弧の閉鎖、statement ID、tag、extensionの妥当性を判定しない。候補をbyte変更せず
Lexer／Parser／Validatorへ渡す。候補でない行へIDや規範強度を要求しない。

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
  "reason": null,
  "operation": {"kind": "THEN", "text": "アクセストークンを1件発行する"},
  "extensions": [],
  "unknownExtensions": [],
  "untrustedText": true,
  "raw": "..."
}
```

Semantic IRはID、source、actor、activation、modality、reason、operation、extensionを保持する。
Lexer token、Markdown装飾、区切り文字の具象nodeは公開Schemaに含めない。

- `text`は正規化後の値を保持する。
- `reason`は`SHOULD`の`[REASON]` text、理由なし`SHOULD`ではnull、`MUST`／`MAY`ではnullとする。
- `raw`は診断と原文参照のため保持する。
- `untrustedText`は常にtrueで、extensionが解除できない。
- JSONをCoreとadapter間の機械契約とする。
- `semanticHash`と`fileHash`を公開fieldにしない。

## 7. ParserとSerializer

- UTF-8を必須とする。
- 候補Scannerを先に適用する。
- ID、重複、tag順序、必須operand、空文字、句点、`SHOULD`理由を検証する。`MUST`または`MAY`の直後に
  `[REASON]`があればtag順序不正として`EAI-CORE-SYNTAX-001`を返す。
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

本表は検索用索引である。draft差分を含む条件ごとの規範値とprimary優先順位は
[Diagnostic registry](../00_共通契約/05_Diagnostic-registry.md)が所有する。

| code | severity | `resultStatus` | 条件 |
|---|---|---|---|
| `EAI-CORE-SYNTAX-001` | error／draftはwarning | `failed`／`passed_with_warnings` | tag順序不正 |
| `EAI-CORE-SYNTAX-002` | error／draftはwarning | `failed`／`passed_with_warnings` | 必須tag不足 |
| `EAI-CORE-SYNTAX-003` | error／draftはwarning | `failed`／`passed_with_warnings` | 発動条件複数 |
| `EAI-CORE-SYNTAX-004` | error／draftはwarning | `failed`／`passed_with_warnings` | 不正escape、未閉鎖quoted value、不正・未閉鎖tag |
| `EAI-CORE-SYNTAX-005` | error／draftはwarning | `failed`／`passed_with_warnings` | 未閉鎖code span |
| `EAI-CORE-SYNTAX-006` | error／draftはwarning | `failed`／`passed_with_warnings` | 句点欠落 |
| `EAI-CORE-ID-001` | error | `failed` | ID形式不正 |
| `EAI-CORE-ID-002` | error | `failed` | 規範文ID重複 |
| `EAI-CORE-SEM-001` | error／draftはwarning | `failed`／`passed_with_warnings` | operand不足 |
| `EAI-CORE-SHOULD-001` | warning | `passed_with_warnings` | `SHOULD`の理由field不足 |
| `EAI-EXT-UNKNOWN-001` | warning | `passed_with_warnings` | opaque extension |

ID系は索引を壊すためdraftでもerrorとする。

## 10. 言語

1 workspace内の規範文を単一言語にすることを推奨し、正本言語は`bitz.yaml.language`で指定する。
Core 1.0は自然言語を決定論的に識別しないため、言語差をDiagnosticまたは合否へ使用しない。
`EAI-CORE-LANG-001`は予約済みとし、公開結果へ返さない。自動翻訳同期と意味的同一性判定も対象外とする。
