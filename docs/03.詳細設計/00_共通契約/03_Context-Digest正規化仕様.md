# コンテキストのハッシュ値の正規化仕様

## 1. 本書の範囲

本書は、コンテキストのハッシュ値（Context Digest）の材料となる入力、正規化、直列化、ハッシュ値の計算を、バイト単位で定義する。
ハッシュ値へ含める材料の選定と除外は[`context`仕様 §6](../03_操作仕様/01_context.md#6-context-digest)が、
複合ワークスペース固有の材料は[複合ワークスペース仕様 §6](../02_SPECモデル/05_複合workspace仕様.md#6-横断索引とcontext)が
所有する。本書は、同じ材料の集合から同じ64桁を得るための手順だけを所有する。

コンテキストのハッシュ値は、`--expect-digest`による取得後の仕様変更の検出、`targetResults[]`の検証証跡、適合fixtureの比較値として
公開する唯一のハッシュ値である。同じCoreのバージョン、同じ入力、同じ実効設定から同じ値を返せない実装は、
Core 1.0に適合しない。

## 2. 全体手順

1. 完全解決が成立し、設定が適合していることを確認する。成立していなければ、ハッシュ値を計算しない。
2. §3の材料を、フィールドの型を保持した、未整列のメモリ上のJSONの値として収集する。
3. §4のフィールドの型ごとの文字正規化を適用する。
4. §3の重複排除と並べ替えを、正規化した後の値へ適用し、最終的なハッシュ値の材料（digest input）を構成する。
5. §5に従い、RFC 8785 JSON Canonicalization Schemeで直列化し、UTF-8のバイト列を得る。
6. バイト列のSHA-256を計算し、小文字の16進64桁へ変換する。
7. `sha256:`を前置した`sha256:[0-9a-f]{64}`を結果へ格納する。

文字正規化より前の値や、ファイルシステム、構文解析器、グラフの走査の列挙順で並べ替えてはならない。正規化により同一になる値が
存在しても、同一の入力から同じ配列とバイト列を得られる順序でなければならない。

## 3. ハッシュ値の材料

ハッシュ値の材料は、次のキーだけを持つJSONのオブジェクトとする。すべてのキーを必須とし、値が空であってもキーを省略しない。

```json
{
  "digestVersion": "1.0",
  "specSchemaVersion": "1.0",
  "earsAiVersion": "1.0",
  "resolverVersion": "1.0",
  "purpose": "implement",
  "requestWorkspaceId": "platform",
  "roots": ["platform::REQ-001:AC-01"],
  "workspaces": [
    {"id": "platform", "path": "."},
    {"id": "web", "path": "apps/web"}
  ],
  "documents": [],
  "crossWorkspaceEdges": [],
  "settings": {}
}
```

| キー | 型 | 内容 |
|---|---|---|
| `digestVersion` | 文字列 | 本仕様の`major.minor`。Core 1.0は`"1.0"` |
| `specSchemaVersion` | 文字列 | 起点ワークスペースの実効の仕様文書のスキーマのバージョン |
| `earsAiVersion` | 文字列 | 起点ワークスペースの実効のEARS-AIのバージョン |
| `resolverVersion` | 文字列 | コンテキスト解決器（Context Resolver）の契約の`major.minor`。Core 1.0は`"1.0"` |
| `purpose` | 列挙値 | `interpret`、`implement`、`verify` |
| `requestWorkspaceId` | 文字列 | 起点ワークスペースの実効ID。単一ワークスペースでも実効IDを使う |
| `roots` | 文字列の配列 | 起点の正規ID。重複排除し、コードポイント辞書順に並べる |
| `workspaces` | オブジェクトの配列 | 到達ワークスペースの`id`とリポジトリのルートからの相対`path`。起点ワークスペースを先頭に置き、以降は`id`の辞書順 |
| `documents` | オブジェクトの配列 | §3.1。`id`のコードポイント辞書順 |
| `crossWorkspaceEdges` | オブジェクトの配列 | §3.2。単一ワークスペースでも空配列を置く |
| `settings` | オブジェクト | §3.3 |

単一ワークスペースでは、`workspaces`を起点ワークスペース1件とし、`path`を`.`とし、`roots`と文書の`id`を非修飾IDにする。
複合ワークスペースでは、両者を修飾IDにする。同じ内容のコンテキストであっても、複合ワークスペース化の前後でハッシュ値は
一致しない。

### 3.1 文書

```json
{
  "id": "web::TECH-010",
  "workspaceId": "web",
  "kind": "technical",
  "status": "approved",
  "applicability": "applicable",
  "frontmatter": {
    "id": "web::TECH-010",
    "title": "Webログイン実装",
    "status": "approved",
    "relations": {
      "requires": [],
      "refines": ["platform::REQ-001:AC-01"],
      "addresses": [],
      "supersedes": [],
      "related": []
    },
    "implements": ["src/auth/login.ts"],
    "tests": [
      {"path": "tests/auth/login.test.ts", "covers": ["platform::REQ-001:AC-01"], "command": "frontend"}
    ],
    "verify": null,
    "changes": []
  },
  "bodyText": "# TECH-010 Webログイン実装\n\n## Context\n\n...",
  "statements": [],
  "strongRelations": [
    {"relation": "refines", "target": "platform::REQ-001:AC-01"}
  ]
}
```

| キー | 型 | 内容 |
|---|---|---|
| `id` | 文字列 | 文書ID。複合ワークスペースでは修飾ID |
| `workspaceId` | 文字列 | 所有ワークスペースの実効ID |
| `kind` | 列挙値 | `requirement`、`technical`、`decision`、`task` |
| `status` | 文字列 | フロントマターの現在の状態 |
| `applicability` | 列挙値 | `applicable`、`advisory`、`replacement` |
| `frontmatter` | オブジェクト | §3.1.1で正規化して抽出した値 |
| `bodyText` | 文字列 | §3.1.2で正規化した本文（body） |
| `statements` | オブジェクトの配列 | §3.1.3。`id`のコードポイント辞書順 |
| `strongRelations` | オブジェクトの配列 | 強い関係。`relation`、`target`の順でコードポイント辞書順に並べ、重複排除する |

`role`、`projection`、到達距離、到達エッジ、コンテキスト一式内の提示順は、ハッシュ値の材料へ含めない。提示の方法の変更で
ハッシュ値を変えないためである。

#### 3.1.1 フロントマターからの抽出

Coreが既知のフィールドだけを、上記の固定したキーで保持する。値の規則は次のとおりとする。

- `id`は複合ワークスペースの正規形式、`title`と`status`は原文を正規化した文字列とする。
- `relations`は、Coreの5つの語彙のキーをすべて置き、未宣言のものは空配列とする。参照先は複合ワークスペースの
  正規形式へ展開し、重複排除してコードポイント辞書順に並べる。
- `implements`と`changes`は、宣言したパスをワークスペースのルートからの相対の`/`区切り文字へ正規化し、
  重複排除して辞書順に並べる。
- `tests`は`path`、`covers`、`command`だけを持つオブジェクトとし、`covers`を修飾IDへ変換してコードポイント辞書順に並べ、
  `command`が未宣言の場合は`null`とする。要素全体は、正規化した後の`(path, commandSortKey, covers)`で昇順に並べる。
  `commandSortKey`は`null`を文字列より前に置き、文字列どうしはコードポイント辞書順とする。`covers`どうしは要素ごとの
  コードポイントの辞書式比較とし、一方が他方の接頭辞であれば短い配列を先にする。完全に同じタプルの要素数は保持し、
  ハッシュ値の生成時に追加の重複排除を行わない。
- `verify`と`changes`は、該当しない種別でもキーを置き、値を`null`または空配列とする。
- `x-`拡張フィールドは含めない。Coreはこれを合否、コンテキスト、コマンド、権限に使わないため、
  コンテキストの同一性の判定にも使わない。
- 未知のフィールドと`profiles`は含めない。

#### 3.1.2 本文

`bodyText`は、フロントマターの終端の区切り行の直後から文書の末尾までを、次の順で正規化した文字列とする。

1. BOMを除く。
2. CRLFとCRをLFへ変換する。
3. 各行の行末の空白類（SPとTAB）を除く。
4. 先頭と末尾の空行を除く。
5. 末尾へLFを1つ置く。本文が空であれば空文字列とする。

Core 1.0は、散文の意味の変更と体裁の変更を区別しない。上記以外の空行の数、見出しの記法、表の桁揃え、語順は
すべてハッシュ値に影響する。過剰に古くなったと判定する方向は安全側であり、変更を見落とす方向は安全側ではない。
除外する節は設けない。Core 1.0は`Revision History`を要求しないため、追記だけを意味の集合の外に置く例外も設けない。

#### 3.1.3 規範文

意味中間表現から、次のキーだけを保持する。

```json
{
  "id": "platform::REQ-001:AC-01",
  "actor": "AuthService",
  "activation": {"kind": "WHEN", "text": "有効な認証情報を受信した場合"},
  "modality": "MUST",
  "reason": null,
  "operation": {"kind": "THEN", "text": "access tokenを1件発行する"},
  "extensions": [
    {"namespace": "quality", "term": "THRESHOLD", "value": "<=200ms"}
  ]
}
```

`documentId`、`localId`、`source`、`raw`、`untrustedText`、`unknownExtensions`は含めない。文書IDは`id`から、
`source`の位置は`bodyText`から導けるためである。`reason`は意味中間表現と同じく、理由付きの`SHOULD`では正規化した後の
テキスト、理由なしの`SHOULD`と`MUST`または`MAY`では`null`とする。`value`を指定していない場合は`null`とする。`extensions`は
正規化した後の`(namespace, term, valueSortKey)`で昇順に並べる。`valueSortKey`は`null`を文字列より前とし、文字列どうしは
コードポイント辞書順とする。完全に同じタプルの要素数は保持する。同じ`namespace`と`term`の組に異なる`value`を持つ拡張タグを
禁止せず、不透明な拡張タグを失わない。不透明な拡張タグの有無はCoreの解析結果の合否を変えないが、ハッシュ値の材料には含める。

`documents[].statements`は、コンテキストが収録する対象規範文ではなく、その文書が所有するすべての規範文とする。
対象規範文の選択はカバレッジと制約台帳が保持し、ハッシュ値の材料にしない。

### 3.2 ワークスペースをまたぐエッジ

[複合ワークスペース仕様 §6](../02_SPECモデル/05_複合workspace仕様.md#6-横断索引とcontext)の
`resolution.crossWorkspaceEdges`と同じ内容、同じ順序、同じ重複排除の規則を使う。
単一ワークスペースでは空配列とする。

### 3.3 設定

`context`仕様 §6の許可リストだけを、キーを固定したオブジェクトとして保持する。

```json
{
  "workspaces": [
    {"id": "platform", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"},
    {"id": "web", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}
  ],
  "context": {"maxDocuments": 20, "maxBytes": 131072},
  "verifyTimeouts": [{"workspaceId": "web", "timeoutSeconds": 300}],
  "commands": [
    {"workspaceId": "web", "name": "frontend", "argv": ["npm", "test", "--", "{tests}"], "cwd": "."}
  ]
}
```

- `workspaces`は、到達ワークスペースだけを`id`の辞書順に並べる。
- `context`は、起点ワークスペースの設定に既定値を適用した後の値だけとする。
- `verifyTimeouts`と`commands`は、目的が`verify`のコンテキスト一式がテスト割当てとして収録したコマンドだけから作る。
  目的が`implement`または`interpret`のコンテキスト一式では、いずれも空配列とする。
- `verifyTimeouts`は、テスト割当てを1件以上収録したワークスペースだけを`workspaceId`の辞書順に並べ、既定値を適用する。
- `commands`は、テスト割当てが参照するコマンドだけを`workspaceId`、`name`の順で辞書順に並べる。`argv`は
  `{tests}`を展開しない引数列テンプレートのまま保持し、`cwd`は未指定のとき`.`とする。
- `multiWorkspace.maxMembers`、`safety`、到達ワークスペースでないワークスペースの設定、使われないコマンド、CLIの`--timeout`の値、
  出力形式、`--report`は含めない。

## 4. 文字正規化

§2の材料の収集の後、並べ替えと直列化の前に、ハッシュ値の材料に含まれるすべての文字列のキーと値へ、次を適用する。

1. Unicode NFCへ正規化する。
2. LFを唯一の改行とする。§3.1.2で正規化済みの`bodyText`は変換し直さない。
3. 次に列挙するパス型のフィールドだけで、U+005C REVERSE SOLIDUSをU+002F SOLIDUSへ変換する。
4. 制御文字を除去または置換せず、トリムと大文字・小文字の変換も行わない。

パスの区切り文字の変換の対象は、次だけである。

- `workspaces[].path`
- `documents[].frontmatter.implements[]`
- `documents[].frontmatter.tests[].path`
- `documents[].frontmatter.changes[]`
- `settings.commands[].cwd`

`title`、`bodyText`、規範文の意味フィールド、拡張タグの`value`、`settings.commands[].argv[]`、ID、ワークスペースID、
関係の参照先は、パスに見える内容を含んでいても区切り文字の変換をしない。フロントマターと設定で`/`を要求する入力のパスは、
通常この変換の前から正規の形であり、本規則はOSの内部表現が混じってもハッシュ値の材料の最終的な境界を固定するために適用する。

配列の重複排除、並べ替え、タプルの比較は、すべて本節で正規化した後の値を使う。正規化により完全に同じオブジェクトとなる複数の要素は、
同じバイト表現になるので、相対の順序がハッシュ値に影響しない。明示的に重複排除を定めた配列以外では、要素数を保持する。

比較のための正規化であり、正本のファイルを書き換えない。

## 5. 直列化とハッシュ値の計算

直列化は、RFC 8785 JSON Canonicalization Schemeに従う。実装は、同等の結果を返す限り
自前の実装でもよいが、次を満たさなければならない。

- 出力はUTF-8とし、BOM、改行、余分な空白を含めない。
- オブジェクトのキーは、UTF-16のコード単位の昇順に並べる。
- 数値は、JSONの数値のうち安全な整数だけを使う。Core 1.0のハッシュ値の材料は、非整数、指数表記、
  `-0`、`NaN`、`Infinity`を持たない。
- 文字列のエスケープは、RFC 8785が要求する最小の集合だけとする。
- 配列は§3で定めた順序を保持し、直列化器が並べ替えない。
- 省略可能なキーを作らない。値がない場合は`null`または空配列を明示する。

ハッシュ値の計算はSHA-256とし、上記のUTF-8のバイト列だけを入力とする。結果は小文字の16進64桁とし、
`sha256:`を前置する。大文字の16進、他のハッシュ関数、切り詰めを使わない。

## 6. 適合

適合する実装は、次を満たす。

- 同じ入力の木構造と同じ実効設定に対し、実行の順序、メモリのキャッシュの使用の有無、ファイルシステム上のパス、ロケール、
  プロセスの環境に依存せず、同じハッシュ値を返す。
- `--detail`、`--expand`、`--format`、`--report`、CLIの`--timeout`の値の変更でハッシュ値を変えない。
- 設定の構文、型、必須のフィールド、参照するコマンドのいずれかが不適合な場合は、ハッシュ値を計算せず、
  不完全な材料からハッシュ値を作らない。
- `digestVersion`、`resolverVersion`、材料の意味を変更する場合は、Coreのメジャーまたはマイナーバージョンを上げ、
  過去のハッシュ値を同じバージョンで再定義しない。

Core 1.0の`digestVersion`と`resolverVersion`は、ともに`"1.0"`であり、パッケージのパッチバージョン、Gitのコミット、実装言語、
設定から導出しない。ハッシュ値の入力構造、正規化、直列化の意味の変更は`digestVersion`を、コンテキストの閉包、適用可能性（applicability）、
対象展開の意味の変更は`resolverVersion`を上げる。パッチリリースではどちらも変更しない。

適合fixtureは、固定した入力に対する期待するハッシュ値を`expected/context.json`へ含める。
fixtureの配置と比較の方法は[適合fixture仕様](04_適合fixture仕様.md)に従う。
