# EARS-AI Core 構文仕様 1.0

## 1. 適用範囲

Coreは全Bitzツールが同じ構造として解析する最小構文を定義する。SDD進行状態、品質指標、DDDモデルなどの固有概念は定義しない。自由記述本文の意味的同一性や正しさはCoreの保証外である。

## 2. 意味軸

### 2.1 ID

規範文には安定IDを付ける。IDは `<文書ID>:<ローカルID>` の**2階層固定**とする
（[ADR-005](../../02.設計書/10_決定記録/ADR-005_規範文IDの階層と記法.md)、
[ADR-013](../../02.設計書/10_決定記録/ADR-013_文書IDとローカルIDの字句規則訂正.md)）。
見出し、背景、理由などの非規範文にはIDを強制しない。

```ebnf
document-id  = prefix, "-", 3*DIGIT ;
prefix       = "REQ" / "TECH" / "ADR" / "TASK" ;
local-id     = ALNUM, *( ALNUM / "-" ) ;            (* AC-01, SPEC-04, CONST-01 *)
statement-id = document-id, ":", local-id ;
```

- 3階層以上のIDを禁止する。1つの発動条件から独立した複数の結果が生じる場合は、発動条件を繰り返した複数の規範文へ分割する。
- IDは同一 `.spec/` 内で一意とする。重複は `EAI-CORE-ID-002` とする。
- IDは永続識別子とし、削除したIDの再利用を禁止する。Coreが機械的に検出するのは、Git基準版に存在し
  現在は削除されているIDの再出現までとする。それ以前の履歴における再利用の禁止はGitレビューの責務とする
  （[ADR-032](../../02.設計書/10_決定記録/ADR-032_ID再利用検出のCore保証範囲.md)）。

### 2.2 ACTOR

`ACTOR` は応答、生成、制約遵守の責任を負う実行主体を表す。作成者、承認者、説明責任者は `ACTOR` へ書かず、Frontmatterの `x-` 拡張（例: `x-owners`）で管理する。これらはCore 1.0の共通項目ではなく、必要なプロジェクトだけが定義する（[Frontmatter共通仕様](../02_SPECファイル規定/03_Frontmatter共通仕様.md) §7）。

### 2.3 発動条件

| タグ | 意味 |
|---|---|
| `ALWAYS` | 常時適用 |
| `WHEN` | イベントまたは条件成立時 |
| `WHILE` | 状態継続中 |
| `WHERE` | 機能・構成・環境が存在する場合 |
| `IF_ERROR` | 異常または望ましくない条件 |

一つのCore文は一つの発動条件を持つ。複数指定は `EAI-CORE-SYNTAX-003` とする。

### 2.4 規範強度

| タグ | 意味 | 判定 |
|---|---|---|
| `MUST` | 必須 | 未充足は `error` |
| `SHOULD` | 推奨 | 不採用理由が記録されていれば `info`、なければ `warning` |
| `MAY` | 任意 | 未実装を不適合としない |

規範強度は省略禁止とする。暗黙の `MUST` は旧版移行時だけ許容する。Core Validatorは構文上の強度を保持し、実装充足の最終判定はテストまたは人間確認へ委ねる。

### 2.5 処理種別

| タグ | 意味 |
|---|---|
| `THEN` | 期待する観測可能な応答 |
| `GENERATE` | 推論を伴う成果物生成 |
| `CONSTRAINT` | 実装・品質・非機能・禁止制約 |

`[MUST] [GENERATE]` は生成処理の実行が必須で、出力内容に非決定性があることを表す。

## 3. 正規構文

### 3.1 文法

```ebnf
statement    = list-marker, SP, "[", statement-id, "]", SP,
               { extension, SP },
               actor, SP,
               activation, SP,
               modality, SP,
               operation,
               period ;

list-marker  = "-" ;
extension    = "[", namespace, ":", term, [ "=", value ], "]" ;
actor        = "[ACTOR:", identifier, "]" ;
activation   = "[ALWAYS]"
             | "[WHEN]",     SP, text
             | "[WHILE]",    SP, text
             | "[WHERE]",    SP, text
             | "[IF_ERROR]", SP, text ;
modality     = "[MUST]" | "[SHOULD]" | "[MAY]" ;
operation    = "[THEN]",       SP, text
             | "[GENERATE]",   SP, text
             | "[CONSTRAINT]", SP, text ;
```

### 3.2 終端記号

```ebnf
SP           = %x20 ;                               (* 半角空白1個。連続は1個へ正規化 *)
UPPER        = %x41-5A ;                            (* A-Z *)
DIGIT        = %x30-39 ;
ALPHA        = UPPER / %x61-7A ;
ALNUM        = ALPHA / DIGIT ;
identifier   = ALPHA, *( ALNUM / "-" / "_" ) ;
namespace    = LOWER, *( LOWER / DIGIT ) ;          (* sdd, quality, ddd *)
LOWER        = %x61-7A ;
term         = UPPER, *( UPPER / DIGIT / "_" ) ;    (* STATE, RETRY_LIMIT *)
value        = bare-value / quoted-value ;
bare-value   = 1*( ALNUM / "-" / "_" / "." ) ;
quoted-value = DQUOTE, *( qchar / escaped ), DQUOTE ;
qchar        = %x20-21 / %x23-5B / %x5D-7E / non-ascii ;   (* " と \ を除く *)
DQUOTE       = %x22 ;
period       = "." / "。" ;
text         = 1*( plain-char / code-span / escaped ) ;
plain-char   = %x20-5A / %x5C-7E / non-ascii ;      (* "[" (%x5B) を除く *)
code-span    = BACKTICK, 1*( %x20-5F / %x61-7E / non-ascii ), BACKTICK ;
escaped      = "\", ( "[" / "]" / "\" / BACKTICK ) ;
BACKTICK     = %x60 ;
non-ascii    = %x80-10FFFF ;
```

### 3.3 字句規則

`text` の終端判定は次の規則で決定論的に行う。

1. Lexerは行を左から右へ1回走査する。
2. **コードスパン内は字句解析の対象外とする。** 開きバッククォート以降、次の閉じバッククォートまでの範囲では、`[` と `]` をタグ区切りとして扱わない。したがって `` `AUTH-503` `` や `` `list[0]` `` はそのまま本文に書ける。
3. コードスパン外で、エスケープされていない `[` に到達した時点で、直前の `text` は終了する。
4. 本文中のリテラル`[`はコードスパンで囲むか`\[`とエスケープする。`]`はそのまま記述でき、`\]`も受理する。エスケープされていない`[`が既知タグとして解釈できない場合は`EAI-CORE-SYNTAX-004`（未閉鎖または不正なタグ）とする。
5. 未閉鎖のコードスパンは `EAI-CORE-SYNTAX-005` とする。
6. `text` の前後の空白を除去する。内部の連続空白は1個へ正規化する。
7. `statement` は1行で完結する。行継続を認めない。
8. 行末の句点（`.` または `。`）を必須とする。欠落は `EAI-CORE-SYNTAX-006` とする。

同じ位置で複数の終端記号へ一致し得る場合は、`code-span`、既知の`escaped`、タグ開始`[`、`plain-char`の順で
字句を確定する。`\`の直後が`[`、`]`、`\`、バッククォート以外なら、`\`を通常文字として扱う。
二重バッククォートによるコードスパンはCore 1.0では扱わない。

### 3.4 解析対象行

規範行候補の抽出と完全な構文検証を分離する
（[ADR-022](../../02.設計書/10_決定記録/ADR-022_規範行候補抽出とID構文検証の分離.md)）。

1. フェンス付きコードブロック（``` および ~~~）と引用ブロック（`>`）の内部は候補にしない。
   仕様書中の記述例が誤って規範文として解釈されることを防ぐ。
2. 先頭の空白を除去した結果が`- [`で始まり、最初の角括弧が次のいずれかなら規範行候補とする。
   - `^[A-Z][A-Z0-9_]*-`で始まり、同じ角括弧内に`:`を持つ文書IDらしいtoken
   - `ACTOR`、`ALWAYS`、`WHEN`、`WHILE`、`WHERE`、`IF_ERROR`、`MUST`、`SHOULD`、`MAY`、
     `THEN`、`GENERATE`、`CONSTRAINT`のCoreタグ
   - `[a-z][a-z0-9]*:`で始まるProfile名前空間形式
3. GFM checkboxの`- [ ]`と`- [x]`（`x`は大文字も含む）は候補から除外する。
4. 候補Scannerは`statement-id`の妥当性を要求しない。候補行をCore Lexer／Parser／Validatorへ渡し、
   prefix、桁数、階層、必須タグ、順序の不正を個別に診断する。
5. 上記に一致しない行は非規範文として扱い、IDや規範強度を要求しない。

したがって`REQ-1:AC-01`、未知prefix、3階層IDは`EAI-CORE-ID-001`、IDを欠いて`ACTOR`などから
始まる候補行は`EAI-CORE-SYNTAX-002`となる。正しいIDへ一致した行だけを候補にしてはならない。

### 3.5 タグ順序

タグは §3.1 の順序で記述する。順序違反は `EAI-CORE-SYNTAX-001` とする。Serializerは正規順序へ整形するが、意味を変更しない（[06_AST・パーサー仕様.md](06_AST・パーサー仕様.md) §5）。

## 4. 例

```markdown
- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 有効な認証情報を受信した場合 [MUST] [THEN] アクセストークンを1件発行する。
- [REQ-001:CONST-01] [ACTOR:AuthService] [ALWAYS] [MUST] [CONSTRAINT] 平文のパスワードを保存しない。
- [TECH-001:SPEC-04] [ACTOR:AuthService] [IF_ERROR] 認証基盤がタイムアウトした場合 [MUST] [THEN] エラーコード `AUTH-503` を返す。
- [TECH-020:SPEC-03] [ACTOR:SpecAgent] [WHEN] 承認済みREQが登録された場合 [MUST] [GENERATE] 対応するTECH仕様案を生成する。
```

同一の発動条件から独立した複数の結果が生じる場合は、発動条件を繰り返して分割する。

```markdown
- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 有効な認証情報を受信した場合 [MUST] [THEN] アクセストークンを1件発行する。
- [REQ-001:AC-02] [ACTOR:AuthService] [WHEN] 有効な認証情報を受信した場合 [MUST] [THEN] 認証成功を監査ログへ1件記録する。
```

## 5. 原子性と文体

- 独立して合否判定できる結果は別IDへ分割する。
- 一文で複数主体へ義務を課さない。
- 型、関数、状態、コード値はバッククォートで囲む。これは可読性のためだけでなく、字句解析上 `[` を含む値を安全に記述する手段でもある（§3.3）。
- 数値条件には単位、比較演算、許容誤差を明示する。
- 「適切に」「必要に応じて」「高速に」など判定不能な表現を禁止する。

## 6. 言語

Core 1.0では、1つの `.spec/` 内の規範文を単一言語にすることを推奨する。正本言語は `.spec/bitz.yaml` の `language` が定める。

同一規範文の自動翻訳同期はCore 1.0の対象外とする（[08_実装ロードマップ.md](../../02.設計書/08_実装ロードマップ.md) §8）。`text` の同一性判定は正規化後の文字列一致で行い、意味的同一性の判定を行わない。この判定は `outdated` 候補の生成に用いる。異なる言語の文書は `EAI-CORE-LANG-001` ／ warning とし、構文解析自体を停止しない。
