# `bitz context`仕様 1.0

## 1. 目的

起点（root）に指定した仕様文書またはEARS-AIの規範文から、解釈・実装・検証に必要な文書を
型付きの関係でたどって完全解決（complete resolution）し、目的に応じたコンテキスト一式（Context Bundle）を返す。
依存の完全解決と、LLMへ提示する量とは分けて扱う。

## 2. 公開操作

```text
bitz context <spec-or-statement-id>...
  [--purpose interpret|implement|verify]
  [--format markdown|json]
  [--detail compact|standard|full]
  [--expand <document-id>]...
  [--expect-digest sha256:<64-lower-hex>]
  [--workspace <workspace-id>]
```

引数列の共通の解析、オプションの重複、空の値、対象の不在は
[Core実行環境・CLI基盤契約 §5・§6](../00_共通契約/06_Core実行環境・CLI基盤契約.md#5-cliの引数列の共通の解析)に従う。
`--purpose`の既定値は`interpret`、`--detail`の既定値は`standard`とする。起点に指定できるのは文書IDと規範文IDだけであり、
パス、コード、テストは指定できない。単一ワークスペースでは非修飾IDだけを受け付ける。複合ワークスペースでは、
作業ワークスペースの非修飾IDまたは修飾IDを受け付け、すべての起点を所有するワークスペースが1つでなければならない。
`--workspace`は非修飾IDを解決する基準のワークスペースを明示するものであり、起点の所有ワークスペース（owner workspace）と
一致しなければならない。`--all-workspaces`は提供しない。複数の起点は重複排除し、正規IDの辞書順に正規化する。

`--format`の既定値は`markdown`である。

起点を1件も指定しない場合と、空文字列を起点に指定した場合は、終了コード4とする。起点が構文上は正しいもののカタログに
存在しない場合は、操作を開始したうえで診断`CTX-ROOT-MISSING-001`（`failed`）を返す。既知の別の起点へ置き換えない。

`--expand`は、完全解決した集合にある文書だけを提示形式（projection）`full`へ昇格する。集合の外のIDは診断
`CTX-PROJECTION-001`（`failed`）とし、暗黙に依存へ加えない。複合ワークスペースでは、非修飾IDの`--expand`を
起点ワークスペースから、修飾IDの`--expand`を複合ワークスペースの軽量な索引から解決する。

## 3. 処理

1. 起点ワークスペース、複合ワークスペースのカタログ、ワークスペースの設定を解決する。
2. 単一ワークスペース、または複合ワークスペースのカタログに含まれるすべての仕様文書から、軽量な索引を作る。
3. ID、型、状態、強い関係、循環を検査する。
4. 対象展開（[`TargetExpansion`](../02_仕様文書モデル/04_関係・トレースモデル.md#64-targetexpansionroot-purpose)）で、起点、
   目的ごとの閉包、対象規範文、隣接規範文を完全解決する。
5. コンテキスト（Context）の上限を検査する。
6. 文書を役割に分類し、制約台帳（Constraint Ledger）とカバレッジを作る。
7. コンテキストのハッシュ値（Context Digest）を計算する。
8. 詳細度（detail）と展開指定（expand）に応じて提示を作る。
9. `--expect-digest`が指定されていれば、現在のハッシュ値と比べる。

強い関係の一部を解決できない場合は、一部が欠けたコンテキスト一式を成功の結果として返さない。
ADRを起点にできるのは、目的が`interpret`のときだけである。ADRに目的`implement`または`verify`を指定した場合は、
対応する対象規範文がないため引数不正として終了コード4とし、結果を作らない。

## 4. コンテキスト一式

```json
{
  "schemaVersion": "1.0",
  "operation": "context",
  "status": "passed_with_warnings",
  "purpose": "implement",
  "workspace": {"id": "root", "path": "."},
  "roots": ["REQ-001"],
  "contextDigest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "revision": {"commit": "0123456789abcdef0123456789abcdef01234567", "dirty": false},
  "resolution": {
    "complete": true,
    "documentCount": 2,
    "unresolvedStrongRelations": 0
  },
  "projection": {"detail": "standard", "expanded": []},
  "documents": [
    {
      "id": "REQ-001",
      "kind": "requirement",
      "status": "approved",
      "role": "root",
      "path": ".spec/requirements/REQ-001.md",
      "projection": "full",
      "reachedBy": ["root"],
      "statementRefs": ["REQ-001:AC-01"],
      "frontmatter": {"id": "REQ-001", "title": "ユーザーログイン", "status": "approved"},
      "bodyText": "# REQ-001 ユーザーログイン\n\n## Intent\n\n認証された利用者へアクセスを提供する。\n",
      "untrustedText": true
    }
  ],
  "constraintLedger": {
    "statements": [
      {
        "id": "REQ-001:AC-01",
        "documentId": "REQ-001",
        "documentRole": "root",
        "modality": "MUST",
        "reason": null,
        "actor": "AuthService",
        "activation": {"kind": "WHEN", "text": "有効な認証情報を受信した場合"},
        "operation": {"kind": "THEN", "text": "access tokenを1件発行する"}
      }
    ]
  },
  "coverage": {
    "must": {
      "total": ["REQ-001:AC-01"],
      "addressed": [],
      "tested": [],
      "unaddressed": ["REQ-001:AC-01"],
      "untested": ["REQ-001:AC-01"]
    },
    "should": {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []},
    "may": {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []},
    "adjacent": []
  },
  "durationMs": 24,
  "diagnostics": []
}
```

`resolution.complete: true`は、型、状態、循環、上限を含めて完全解決が成立したことを示す。
`constraintLedger`は、適用可能な文書が持つ対象規範文を、意味中間表現の意味フィールドで
1回だけ保持する。隣接規範文と、適用可能性が`advisory`の文書の規範文は、制約台帳にも、
カバレッジの各規範強度にも含めない。
`coverage.adjacent`は`TargetExpansion`の`adjacentStatements`を同じ順序で保持し、該当がなければ空配列とする。
`reason`はすべての規範文で必須とし、理由付きの`SHOULD`では正規化した後のテキスト、それ以外では`null`とする。
複合ワークスペースでは、最上位の`workspace`を起点ワークスペースとし、`roots`、文書の`id`、規範文IDを修飾IDで返す。
`documents[]`の各要素は`workspaceId`を持ち、`path`はそのワークスペースのルートからの相対パスとする。
`resolution.workspaces`と`resolution.crossWorkspaceEdges`のフィールド、内容、順序は
[複合ワークスペース仕様](../02_仕様文書モデル/05_複合ワークスペース仕様.md)に従い、複合ワークスペースの結果では必須とする。

複合ワークスペースの結果に加わるスキーマを次に示す。単一ワークスペースでは、これらのフィールドを省略する。

| フィールド | 型 | 必須 | 内容 |
|---|---|:--:|---|
| `documents[].workspaceId` | 文字列 | ○ | 所有ワークスペースのID。文書の`id`は修飾ID |
| `resolution.workspaces` | オブジェクトの配列 | ○ | 到達ワークスペース。1件以上。起点ワークスペースを先頭に置き、以降はIDの辞書順 |
| `resolution.workspaces[].id` | 文字列 | ○ | 重複しないワークスペースID |
| `resolution.workspaces[].path` | 文字列 | ○ | リポジトリのルートからの相対パス。ルートワークスペースは`.` |
| `resolution.crossWorkspaceEdges` | オブジェクトの配列 | ○ | ワークスペースをまたぐエッジ。0件でも空配列 |
| `crossWorkspaceEdges[].relation` | 列挙値 | ○ | `requires`、`refines`、`addresses`、`supersedes`、`related` |
| `crossWorkspaceEdges[].source` | 文字列 | ○ | 修飾した文書ID |
| `crossWorkspaceEdges[].target` | 文字列 | ○ | 修飾した文書IDまたは規範文ID |

エッジは重複排除し、`source`、`relation`、`target`の辞書順とする。ワークスペースの境界を越えないエッジは収録しない。

## 5. 提示形式

どの提示形式でも、`id`、`kind`、`status`、`role`、`path`、`projection`、`reachedBy[]`、`untrustedText: true`を必須とする。
`reachedBy[]`には、起点であれば`root`を入れ、到達したエッジごとに`<relation>:<source-id>`を入れる。
重複排除した後のコードポイント辞書順とする。`source-id`は、規範文単位の関係（`refines`の参照先が規範文である場合など）でも、
その関係を宣言した文書のID（規範文IDではない）とする。

| 提示形式 | 追加で必須のフィールド | 禁止するフィールド |
|---|---|---|
| `full` | `statementRefs[]`、`frontmatter`、`bodyText` | `expandable` |
| `normative` | `statementRefs[]` | `frontmatter`、`bodyText`、`expandable` |
| `reference` | `expandable` | `statementRefs`、`frontmatter`、`bodyText` |

`statementRefs[]`は、その文書が所有するすべての規範文のIDを、行番号、IDの順で保持する。対象規範文かどうかで絞り込まない。
`frontmatter`は許可されたフィールドを正規化したオブジェクト、`bodyText`は原文の現行本文とする。
`expandable`は、完全解決した集合の中にあって`--expand`で指定できる場合に`true`とする。
省略の代わりに`null`を出力せず、禁止するフィールドは出力しない。
役割の割当ては[関係・トレースモデル §7](../02_仕様文書モデル/04_関係・トレースモデル.md#7-決定論的探索)に従う。

詳細度`standard`では、文書の役割で既定の提示形式を決める。提示形式を`full`にするのは、起点（`root`）、
TASK（`work`）、後継（`replacement`）、要求（`requirement`）、制約（`constraint`）と、距離1の文書である。
`normative`にするのは、それ以外の距離2以上の具体化文書である（その規範文は制約台帳に収録される）。
`reference`にするのは役割`advisory`の文書である。詳細度`compact`では原文を省略し、`Bundle Manifest`、診断、
制約台帳、カバレッジ、境界、参照を返し、すべての文書を提示形式`reference`にする。詳細度`full`では、
解決したすべての文書を提示形式`full`にする。

役割`requirement`と`constraint`の文書を`normative`ではなく`full`にするのは、`requires`または`addresses`で到達したそれらの文書が所有する規範文は
`targetStatements`へ昇格せず（[関係・トレースモデル §6.4](../02_仕様文書モデル/04_関係・トレースモデル.md#64-targetexpansionroot-purpose)
の規則4）、制約台帳に収録されない（本仕様§4）ためである。`normative`にすると、それらが持つ`MUST`の本文が
提示からも制約台帳からも失われ、依存の距離を理由に必須の制約を参照だけへ落とさないという、ADR-014の`Decision`の4番目の項目に
反する。役割を先に適用し（`root`、`work`、`replacement`、`requirement`、`constraint`は`full`、`advisory`は`reference`）、
依存の距離は具体化文書を
`full`と`normative`に分けるときだけ使うという本節の規則は、ADR-014の`Decision`の5番目の項目と整合する。

どの詳細度でも、完全解決、`MUST`の対象規範文すべて、制約台帳を省略しない。提示の方法を変えても、コンテキストのハッシュ値は
変わらない。Core 1.0は提示内容のハッシュ値（Projection Digest）を返さない。

## 6. コンテキストのハッシュ値

コンテキストのハッシュ値は、次の材料を正規JSONにしたもののSHA-256である。
形式は`sha256:[0-9a-f]{64}`とする。

- 仕様文書のスキーマ、EARS-AI、コンテキスト解決器のバージョン
- 目的、起点ワークスペースのID、起点の正規ID
- 閉包に含まれる文書のID、種別、状態、適用可能性、正規化したフロントマター、現行本文の意味内容
- 強い関係
- EARS-AIの意味中間表現が持つ正規の意味フィールド
- `implements`、テスト対応、コマンド名、引数列テンプレート、作業ディレクトリ、
  設定したタイムアウト、TASKの`changes`
- コンテキストに影響する実効設定
- 到達ワークスペースのID、リポジトリのルートからの相対パス、修飾したエッジ

「コンテキストに影響する実効設定」は、到達ワークスペースの設定全体ではなく、次の許可リストとする。

- 到達ワークスペースごとの`schemaVersion`、`earsAi`、`language`
- 起点ワークスペースだけの`context.maxDocuments`と`context.maxBytes`（既定値を適用した後の値）
- 目的が`verify`のコンテキスト一式では、テスト割当てを1件以上収録したワークスペースの`verify.timeoutSeconds`
  （既定値を適用した後の値）。目的が`implement`または`interpret`のときは空配列とする
- 目的が`verify`のコンテキスト一式では、収録したテスト割当てが参照するコマンドだけの名前、引数列テンプレート、
  作業ディレクトリ（既定値を適用した後の値）。コマンド名の辞書順とする。目的が`implement`または`interpret`のときは空配列とする

次は含めない。

- 生成時刻、絶対パス、キャッシュの位置、出力形式
- 詳細度、展開指定、各文書の提示形式、実際の提示内容
- Git、PR、ADRにある変更履歴
- コードとテストのファイルの内容
- CLIの`--timeout`の値
- 到達ワークスペースでないワークスペースの設定と本文、カタログでの列挙順
- `multiWorkspace.maxMembers`、使われないコマンド、`safety`

設定の構文、型、必須フィールド、参照するコマンドのいずれかが不適合であれば、ハッシュ値を計算する前に停止し、
不完全な設定からハッシュ値を作らない。

公開するハッシュ値はコンテキストのハッシュ値だけとする。文書単位のハッシュ値と提示内容のハッシュ値は内部実装にとどめる。

## 7. 取得後の仕様変更の検出

アダプターは、最初の書込みの直前と、仕様または設定の変更を認識して作業を再開するときに、同じリクエストを
`--expect-digest`付きで再実行し、取得後の仕様変更を検出する（stale detection）。ハッシュ値が一致しなければ診断`CTX-STALE-001`（`blocked`）とし、
新しい仕様を暗黙に受け入れない。

## 8. 上限

上限の既定値は20文書と128 KiB、絶対上限は100文書と1 MiBとする。意味上の依存には深さの上限を設けない。
完全な閉包が上限を超えた場合は、診断`CTX-LIMIT-001`（`blocked`）とする。バイト数の上限は、指定した`--detail`に
かかわらず、詳細度`standard`で提示したときの量
（[安全な入出力 §4「コンテキストの意味中間表現と標準の提示」](../00_共通契約/02_安全な入出力・互換性.md#4-リソースの上限)）で測る。
詳細度または展開指定だけが原因で提示量が絶対上限を超えた場合は、診断`CTX-PROJECTION-LIMIT-001`（`failed`）とする。

## 9. Markdownでの提示

Markdownでの提示は結果のJSONだけを入力とする表示であり、結果の状態、件数、終了コード、コンテキストのハッシュ値を変えない。
同じ結果からは同じバイト列を生成する。

### 9.1 全体の規則

1. 改行はLFとし、出力はLF 1個で終わる。CRを出力しない。
2. H1は`# Context Bundle`だけとする。§9.2の10個の節はH2、文書と規範文の明細はH3とする。
3. 見出しの前後に空行を1行置く。空行を2行以上続けない。
4. 一覧の項目は`- <key>: <value>`とし、字下げしない。値のないフィールドは`null`、空配列は`none`と書く。
5. 複数の値は、結果のJSONの配列の順のまま`, `で連結する。表示の側で並べ替えない。
6. 該当する要素のない節も見出しを省略せず、本文を`- none`の1行とする。
7. `durationMs`を提示しない。可変幅の桁揃え、装飾、進捗表示を出力しない。

### 9.2 節と出所

| # | 節 | 出所 |
|---:|---|---|
| 1 | `Bundle Manifest` | `operation`、`status`、`purpose`、`workspace`、`roots`、`contextDigest`、`revision`、`resolution`、`projection` |
| 2 | `Diagnostics and Coverage Gaps` | `diagnostics[]`、`coverage`の`unaddressed`と`untested` |
| 3 | `Normative Constraint Ledger` | `constraintLedger.statements[]` |
| 4 | `Root Intent` | 役割が`root`の文書 |
| 5 | `Required Context` | 役割が`requirement`または`constraint`の文書 |
| 6 | `Applicable Refinements` | 役割が`refinement`の文書 |
| 7 | `Replacement Candidates` | 役割が`replacement`の文書 |
| 8 | `Work Boundary` | 役割が`work`の文書 |
| 9 | `Verification Bindings` | 本文を提示した文書の`frontmatter.tests[]` |
| 10 | `Advisory Documents` | 役割が`advisory`の文書 |

文書は`documents[]`の順のまま該当する節へ振り分け、節の中で並べ替えない。

### 9.3 `Bundle Manifest`

`operation`、`status`、`purpose`、`roots`、`contextDigest`をJSONの値のまま1行ずつ出す。
`workspace`は`<id> (<path>)`、`revision`は存在すれば`<commit> dirty=<true|false>`、なければ`null`とする。
`resolution`は`complete=<bool>, documentCount=<n>, unresolvedStrongRelations=<n>`、
`projection`は`detail=<detail>, expanded=<ids|none>`とする。

### 9.4 `Diagnostics and Coverage Gaps`

診断は、[結果・診断・終了コードの仕様 §7](../00_共通契約/01_結果・診断・終了コード.md#7-テキストとjson)のテキスト行の形式で、
`- `に続けて1件1行で出す。JSONでの順序と、制御文字の可視化の規則をそのまま使う。`suggestedAction`を持つ行の直後には、
半角スペース2個で字下げした`-> `の継続行を1行出す。続けて、カバレッジの不足（coverage gap）を`- coverage: <MODALITY> <bucket>: <ids>`の形で、
規範強度は`must`、`should`、`may`の順、各規範強度の中は`unaddressed`、`untested`の順に出す。0件の`<bucket>`は行を出さない。

### 9.5 `Normative Constraint Ledger`

規範文ごとに`### <statement-id>`を置き、`documentId`、`documentRole`、`modality`、`reason`、`actor`、
`activation`、`operation`を1行ずつ出す。`activation`と`operation`は、テキストがなければ`<kind>`、
あれば`<kind> <text>`とし、テキストは正規化した後の値をそのまま出す。

### 9.6 文書の節

文書ごとに`### <id> — <path>`を置く。複合ワークスペースでは`id`が修飾IDであり、その値をそのまま見出しに使う。
提示形式ごとに次のフィールドを出し、[§5](#5-提示形式)で禁止したフィールドは出力しない。

| フィールド | `full` | `normative` | `reference` |
|---|:--:|:--:|:--:|
| `kind`、`status`、`projection`、`reachedBy`、`untrustedText` | ○ | ○ | ○ |
| `statementRefs` | ○ | ○ | — |
| `frontmatter` | ○ | — | — |
| `expandable` | — | — | ○ |
| `bodyText` | ○ | — | — |

出力するフィールドの並びは`kind`、`status`、`projection`、`reachedBy`、`statementRefs`、`frontmatter`、
`untrustedText`、`expandable`、`bodyText`の順に固定し、上の表で禁止されるフィールドは省く。

`frontmatter`は`- frontmatter: <Canonical JSON>`の1行とし、[§6](#6-コンテキストのハッシュ値)の正規JSONの規則を使う。
YAMLへ直列化し直さない。`bodyText`は、`- bodyText:`の行と空行1行に続けて、フェンスで囲んで出す。フェンスは
情報文字列`markdown`を付けたバッククォートの連なりとし、その長さは本文中で最も長いバッククォートの連なりより1つ長く、
最小3とする。本文のコードポイントを変えず、本文の末尾が改行でなければ、フェンスの直前に改行を1個だけ補う。
本文の制御文字を可視化せず、原文のまま提示する。
詳細度が`compact`のときは文書の節の見出しを残し、本文を`- <id>: <path>`の1行だけとする。

### 9.7 `Verification Bindings`

本文を提示した文書の`frontmatter.tests[]`を、文書の順と配列の順のまま
`- <path>: covers <ids> (command: <name|none>)`の形で出す。本文を提示していない文書からは補わない。

アダプターの指示はコンテキスト一式の外から与え、本文をアダプターのシステム指示へ昇格しない。

## 10. 診断

| 診断コード | 結果 | 条件 |
|---|---|---|
| `CTX-ROOT-MISSING-001` | `failed` | 起点のIDが存在しない |
| `SPEC-RELATION-MISSING-001` | `failed` | 存在するワークスペースの中に、強い関係の参照先が存在しない |
| `CTX-RELATION-TYPE-001` | `failed` | 関係型が不正 |
| `CTX-CYCLE-001` | `failed` | 禁止された循環がある |
| `CTX-TASK-DEPENDENCY-001` | `blocked` | 先行するTASKが完了していない |
| `CTX-STATE-001` | `blocked` | 目的に適用できない |
| `CTX-STATE-SUPERSEDED-001` | `blocked` | 起点または依存先が置換済み |
| `CTX-STATE-SUPERSEDED-002` | `failed` | 有効な後継が複数ある |
| `CTX-LIMIT-001` | `blocked` | 完全な閉包が上限を超えた |
| `CTX-COVERAGE-TASK-001` | `passed_with_warnings` | 目的`implement`の対象の`MUST`が未対応 |
| `CTX-COVERAGE-TEST-001` | 警告／`blocked` | 目的`implement`では警告、`verify`では`blocked` |
| `CTX-STALE-001` | `blocked` | 期待したハッシュ値と一致しない |
| `CTX-PROJECTION-001` | `failed` | 展開指定の対象が解決した集合の外にある |
| `CTX-PROJECTION-LIMIT-001` | `failed` | 提示量が絶対上限を超えた |

強い関係の参照先の不在は`SPEC-RELATION-MISSING-001`に統一し、`CTX-RELATION-MISSING-001`は公開結果で使わない。
修飾ID、ワークスペース、参照先、型に関する主診断の優先順位は
[関係・トレースモデル](../02_仕様文書モデル/04_関係・トレースモデル.md#51-関係の診断の優先順位)に従う。
この表は検索用の索引である。すべての条件の診断コード、重大度、結果への効果（`resultStatus`）、
発生元、継続単位、主診断の優先順位は、[診断レジストリ](../00_共通契約/05_診断レジストリ.md)が所有する。


## 11. アダプターとの契約

アダプターは、実装の前に目的`implement`のコンテキスト一式を取得し、結果の状態が`passed`または`passed_with_warnings`で、
かつ`resolution.complete: true`である場合にだけ書込みを始める。状態が`failed`、`blocked`、`error`の場合と、
引数不正の場合は停止する。すべての`MUST`、制約、作業境界（work boundary）、カバレッジの不足を計画に反映し、提示形式が`reference`の
文書の内容を推測しない。実装の後は`check`を実行し、完了の前に目的`verify`のコンテキスト一式を解決し直して`verify`を呼ぶ。
`check`と`verify`も、通過状態である`passed`または`passed_with_warnings`の場合にだけ次の段階へ進める。
