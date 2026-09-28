# EARS-AI言語・意味中間表現仕様 1.0

## 1. 適用範囲

EARS-AI Coreは、Bitzのすべての操作が同じ構造として解析する最小の要求言語を定義する。自由記述の意味的正しさ、
SDDフロー、品質指標、DDDモデルは定義しない。

Markdownは人間が編集する正本であり、意味中間表現（Semantic IR）は決定論的な検査、コンテキスト、トレースに使う派生表現である。
意味中間表現を正本のファイルとして保存しない。

## 2. 意味軸

### 2.1 ID

規範文ID（statement ID）は`<document-id>:<local-id>`の2階層固定とする。

```ebnf
document-id  = prefix, "-", digit, digit, digit, { digit } ;
prefix       = "REQ" | "TECH" | "ADR" | "TASK" ;
local-id     = upper, { upper | digit | "-" }, "-", digit, digit, { digit } ;
statement-id = document-id, ":", local-id ;
```

- 規範文（statement）だけにIDを要求する。
- 3階層以上のIDを禁止する。
- 同一ワークスペース内で一意とする。
- 削除したIDを別の意味へ再利用しない。
- 独立して合否判定できる結果は別IDに分ける。

### 2.2 実行主体

実行主体（actor）は、応答、生成、制約の遵守に責任を負う主体である。作成者、承認者、所有チームではない。

### 2.3 発動条件

| タグ | 意味 |
|---|---|
| `ALWAYS` | 常時適用 |
| `WHEN` | イベントの発生または条件の成立 |
| `WHILE` | 状態が続いている間 |
| `WHERE` | 機能・構成・環境が存在する場合 |
| `IF_ERROR` | 異常または望ましくない条件 |

1文は1つの発動条件（activation）を持つ。

### 2.4 規範強度

| タグ | 意味 | 未充足 |
|---|---|---|
| `MUST` | 必須 | `error` |
| `SHOULD` | 推奨 | `[REASON]`なしは診断`EAI-CORE-SHOULD-001`（重大度`warning`） |
| `MAY` | 任意 | 不適合にしない |

規範強度（modality）の省略を禁止する。`SHOULD`の理由（reason）は`[SHOULD] [REASON] <text>`で明示する。
理由なしの`[SHOULD]`も構文解析して意味中間表現の`reason`を`null`にするが、重大度`warning`を返す。
`MUST`と`MAY`へ`[REASON]`を付けてはならない。Coreは強度と理由を保持するが、実装充足はテストまたは人間確認で判断する。

### 2.5 処理種別

| タグ | 意味 |
|---|---|
| `THEN` | 観測可能な応答 |
| `GENERATE` | 推論を伴う成果物生成 |
| `CONSTRAINT` | 実装・品質・非機能・禁止制約 |

## 3. 正規構文

本節はISO/IEC 14977相当のEBNFだけを使用する。`,`は連接、`|`は選択、`[ ... ]`は省略可能、
`{ ... }`は0回以上の繰返し、`;`は規則の終端、引用符の中は終端記号を表す。ABNFの`%x`、`n*element`、`/`は使用しない。
入力は妥当なUTF-8から復号したUnicodeのスカラー値の列とし、文法は1コードポイント単位で評価する。

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

`plain-char`は`[`、`\\`、バッククォート、CR、LF以外のUnicodeのスカラー値である。`]`は単独の通常文字として許可する。
`qchar`は`DQUOTE`、`\\`、CR、LF以外、`code-char`はCR、LF以外のUnicodeのスカラー値である。
これらの3つは否定集合であるため、上の有限な生成規則とは分けて定義する。

`backtick-run`は、連続するバッククォートの極大な連続列として読み取る。開始した連続列と同じ個数のバッククォートから成る
最初の連続列だけを終了の区切り文字とする。
異なる長さの連続列は`code-char`として保持する。コードスパンの中では、エスケープとタグを解釈しない。
意味中間表現の`text`には、開始・終了のバッククォートの連続列を除いた内容だけを保持する。内部にある異なる長さの連続列は残す。
コードスパンの外の`text`と連結した後、§4のSP／TABの正規化を適用する。区切りを含む原文は`raw`と文書の本文へ保持する。
`text`の終了位置は、次に現れる未エスケープの既知のタグの開始位置で決める。`operation`の`text`では、コードスパンの外にある
行末の直前にある最後の`.`または`。`を`period`とし、それより前を`text`とする。空の`text`は許可しない。

`quoted-value`の中の`escaped`は、エスケープ後の1コードポイントを値へ保持する。`text`の中でも同じ解除を行う。
未知のエスケープ、未閉鎖の`quoted-value`、開始した連続列と同じ長さの終了する連続列がないコードスパン、未閉鎖のタグは受理しない。

拡張タグ（extension）はCore 1.0では不透明な値として保持する。Coreはプロファイルマニフェスト、外部の検証プログラム、
プロファイル固有の移行を読み込まない。
未知の名前空間は診断`EAI-EXT-UNKNOWN-001`（重大度`warning`）とし、Coreの構文解析を続ける。

## 4. 字句規則

1. 規範文は1行で完結し、行継続を認めない。
2. コードスパンの中の`[`と`]`をタグの区切りとして扱わない。
3. コードスパンの外にある未エスケープの`[`で、直前の`text`を終了する。
4. リテラルの`[`は、コードスパンまたは`\[`で書く。`\]`、`\\`、``\` ``も受理する。
5. 未閉鎖のタグは診断`EAI-CORE-SYNTAX-004`、未閉鎖のコードスパンは診断`EAI-CORE-SYNTAX-005`とする。
6. `text`の前後のSPとTABを除去し、内部で連続するSP／TABを1個のSPへ正規化する。それ以外のUnicodeの空白文字は保持する。
7. 行末の`.`または`。`を必須とする。
8. タグの順序は、ID、拡張タグ、実行主体、発動条件、規範強度、処理種別（operation）とする。

字句解析器（Lexer）は、行を左から右へ1回走査し、`TEXT`、`CODE_SPAN`、`TAG`、`SP`、`PERIOD`のトークンを返す。
同じ位置で複数が一致する場合は、コードスパン、既知のエスケープ、タグの開始、`period`、通常の文字の順で確定する。
`PERIOD`にするのは、コードスパンの外にある行末の`.`または`。`だけであり、それ以外の句点は`TEXT`へ含める。
`quoted-value`の中では`DQUOTE`、既知のエスケープ、`qchar`の順とする。トークンの開始・終了オフセットと、診断の行番号・列番号は、
Unicodeのコードポイント単位の1始まりとし、TAB、結合文字、全角文字も各1列と数える。改行のコードポイントはトークンに含めない。

同じ元の原因から複数の構文候補が生じる場合は、未閉鎖のコードスパン、未閉鎖または不正なタグ、ID形式、タグの順序、
必須タグの不足、発動条件が複数、句点の欠落、オペランドの不足の順で、主診断を1件だけ返す。別の位置にある独立した原因は、
それぞれ返す。
[診断レジストリ](../00_共通契約/05_Diagnostic-registry.md)の`priority`は、この順序と一致させる。

期待するタグの出現位置に別のタグが現れた場合は、次のいずれかで判定する。

1. 期待するタグが同じ行の後方（コードスパンの外）に存在する場合は、タグの順序が不正（`EAI-CORE-SYNTAX-001`）とする。
2. 期待するタグが同じ行のどこにも存在しない場合は、必須タグの不足（`EAI-CORE-SYNTAX-002`）とする。
3. その位置のタグがCoreタグでも妥当な拡張タグでもない場合は、不正なタグ（`EAI-CORE-SYNTAX-004`）とする。

この規則は、`operation`の後に続くタグ（末尾の拡張タグを含む）にも、同じ順序で適用する。

## 5. 規範文の候補

候補抽出（candidate extraction）と、完全な構文検証を分離する。

走査器（Scanner）はLFへ改行を正規化した後、次の状態機械を文書の先頭から行単位で実行する。

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

開始フェンスの連続列の後に情報文字列があっても、開始とみなす。終了フェンスに情報文字列は許可しない。
引用とは、先頭の0〜3個のSPの直後が`>`である行を指し、引用の中のリストを候補にしない。TABを字下げまたはSPとして扱わない。
`cursor + 3`は、最初の`[`の1始まりの列である。

`IsCandidateToken`は、次のいずれかを満たす場合だけ`true`とする。判定はASCIIで、大文字と小文字を区別し、
トークンの妥当性を要求しない。

1. `REQ`、`TECH`、`ADR`、`TASK`のいずれかで始まる。
2. ASCIIの大文字で始まり、`-`または`:`を1個以上含む。未知の接頭辞、桁数の不足、3階層のIDを候補に残すための規則である。
3. `ACTOR`、`ALWAYS`、`WHEN`、`WHILE`、`WHERE`、`IF_ERROR`、`MUST`、`SHOULD`、`MAY`、
   `REASON`、`THEN`、`GENERATE`、`CONSTRAINT`のいずれかで始まる。IDの欠落と、不正なCoreタグを候補に残す。
4. `lower, { lower | digit }, ":"`に一致する接頭辞を持つ。拡張タグから始まるIDの欠落を候補に残す。

走査器は、角括弧の閉鎖、規範文ID、タグ、拡張タグの妥当性を判定しない。候補を1バイトも変更せず、
字句解析器／構文解析器（Parser）／検証プログラムへ渡す。候補でない行へ、IDや規範強度を要求しない。

これにより、桁数の不足、未知の接頭辞、3階層のID、IDの欠落を、通常の本文として見逃さない。

## 6. 意味中間表現

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

意味中間表現は、`id`、`source`、`actor`、`activation`、`modality`、`reason`、`operation`、`extensions`を保持する。
字句解析器のトークン、Markdownの装飾、区切り文字の具象ノードは、公開スキーマに含めない。

- `text`は正規化後の値を保持する。
- `reason`は、`SHOULD`の`[REASON]`の`text`とし、理由のない`SHOULD`では`null`、`MUST`または`MAY`では`null`とする。
- `extensions`は、出現順の`{namespace, term, value}`の配列とし、値の指定がない場合は`null`、`quoted-value`の場合は
  エスケープを解除した後の文字列を保持する。
- `unknownExtensions`は、`extensions`のうち`namespace`が未知の要素を、同じオブジェクトの形、出現順で保持する。重複も保持する。
- `raw`は診断と原文参照のため保持する。
- `untrustedText`は常に`true`とし、拡張タグで解除できない。
- JSONを、Coreとアダプターの間の機械契約とする。
- `semanticHash`と`fileHash`は、公開フィールドにしない。

## 7. 構文解析器と直列化器

- UTF-8を必須とする。
- 走査器による候補抽出を先に適用する。
- ID、重複、タグの順序、必須のオペランド、空の文字列、句点、`SHOULD`の理由を検証する。`MUST`または`MAY`の直後に
  `[REASON]`があれば、タグの順序が不正として診断`EAI-CORE-SYNTAX-001`を返す。
- `source`の位置を、行・列単位で保持する。
- 不透明な拡張タグを失わない。
- 拡張タグの有無で、Coreの解析結果を変えない。
- ネットワークとAIの推論を使わない。
- 同一の入力、同一のバージョンから、同一の意味中間表現を返す。

直列化器（Serializer）は、正規のタグの順へ整形できるが、意味を変更しない。整形による変更と内容の変更を同じパッチへ混ぜず、
不透明な拡張タグを削除しない。Core 1.0は、公開の`bitz fmt`を提供しない。

## 8. 原子性と文体

- 独立して失敗、変更、検証できる結果は別IDへ分割する。
- 1つの文で、複数の実行主体へ義務を課さない。
- 型、関数、状態、コードの値は、コードスパンにする。
- 数値条件は単位、比較演算、許容誤差を明示する。
- 「適切に」「必要に応じて」「高速に」など判定不能な表現を避ける。

## 9. 診断

本表は検索用の索引である。`draft`の差分を含む、条件ごとの規範値と主診断の優先順位は、
[診断レジストリ](../00_共通契約/05_Diagnostic-registry.md)が所有する。

| コード | 重大度 | 結果への効果 | 条件 |
|---|---|---|---|
| `EAI-CORE-SYNTAX-001` | `error`／`draft`は`warning` | `failed`／`passed_with_warnings` | タグの順序が不正 |
| `EAI-CORE-SYNTAX-002` | `error`／`draft`は`warning` | `failed`／`passed_with_warnings` | 必須タグの不足 |
| `EAI-CORE-SYNTAX-003` | `error`／`draft`は`warning` | `failed`／`passed_with_warnings` | 発動条件が複数 |
| `EAI-CORE-SYNTAX-004` | `error`／`draft`は`warning` | `failed`／`passed_with_warnings` | 不正なエスケープ、未閉鎖の`quoted-value`、不正または未閉鎖のタグ |
| `EAI-CORE-SYNTAX-005` | `error`／`draft`は`warning` | `failed`／`passed_with_warnings` | 未閉鎖のコードスパン |
| `EAI-CORE-SYNTAX-006` | `error`／`draft`は`warning` | `failed`／`passed_with_warnings` | 句点の欠落 |
| `EAI-CORE-ID-001` | `error` | `failed` | ID形式が不正、または規範文IDの文書部分がフロントマターの`id`と不一致（`draft`でも`error`とする） |
| `EAI-CORE-ID-002` | `error` | `failed` | 規範文IDの重複 |
| `EAI-CORE-SEM-001` | `error`／`draft`は`warning` | `failed`／`passed_with_warnings` | オペランドの不足 |
| `EAI-CORE-SHOULD-001` | `warning` | `passed_with_warnings` | `SHOULD`の理由フィールドの不足 |
| `EAI-EXT-UNKNOWN-001` | `warning` | `passed_with_warnings` | 不透明な拡張タグ |

ID系は、索引を壊すため、`draft`でも`error`とする。

## 10. 言語

1つのワークスペースの中にある規範文は単一の言語にすることを推奨し、正本言語（language）は`bitz.yaml.language`で指定する。
Core 1.0は自然言語を決定論的に識別しないため、言語の違いを診断または合否の判定に使わない。
`EAI-CORE-LANG-001`は予約済みとし、公開結果へ返さない。自動翻訳の同期と、意味的な同一性の判定も対象外とする。
