# Context Digest正規化仕様

## 1. 所有範囲

本書はContext Digestの入力document、正規化、serialization、hash計算をbyte単位で定義する。
Digestへ含める材料の選定と除外は[context仕様 §6](../03_操作仕様/01_context.md#6-context-digest)、
連合固有の材料は[モノレポSPEC連合仕様 §6](../02_SPECモデル/05_モノレポSPEC連合仕様.md#6-横断索引とcontext)が
所有する。本書は同じ材料集合から同じ64桁を得るための手順だけを所有する。

Context Digestは`--expect-digest`によるstale検出、`targetResults[]`の検証証跡、適合fixtureの比較値として
公開する唯一のhashである。同じCore version、同じ入力、同じ実効設定から同じ値を返せない実装は
Core 1.0適合ではない。

## 2. 全体手順

1. 完全解決が成立し、設定が適合していることを確認する。不成立ならDigestを計算しない。
2. §3のdigest inputをmemory上のJSON valueとして構成する。
3. 全stringへ§4の文字正規化を適用する。
4. §5に従いRFC 8785 JSON Canonicalization Schemeでserializeし、UTF-8 byte列を得る。
5. byte列のSHA-256を計算し、小文字16進64桁へ変換する。
6. `sha256:`を前置した`sha256:[0-9a-f]{64}`を結果へ格納する。

## 3. digest input

digest inputは次のkeyだけを持つJSON objectとする。全keyを必須とし、値が空でもkeyを省略しない。

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

| key | 型 | 内容 |
|---|---|---|
| `digestVersion` | string | 本仕様のmajor.minor。Core 1.0は`"1.0"` |
| `specSchemaVersion` | string | request workspaceの実効SPEC Schema version |
| `earsAiVersion` | string | request workspaceの実効EARS-AI version |
| `resolverVersion` | string | Context Resolverのmajor.minor |
| `purpose` | enum | `interpret`、`implement`、`verify` |
| `requestWorkspaceId` | string | request workspaceの実効ID。単一workspaceも実効IDを使う |
| `roots` | string[] | 起点の連合正規ID。重複排除しcode point辞書順 |
| `workspaces` | object[] | 到達workspaceの`id`とrepository root相対`path`。request workspaceを先頭、以降`id`辞書順 |
| `documents` | object[] | §3.1。`id`のcode point辞書順 |
| `crossWorkspaceEdges` | object[] | §3.2。単一workspaceでも空配列を置く |
| `settings` | object | §3.3 |

単一workspaceでは`workspaces`をrequest workspace1件、`path`を`.`とし、`roots`と文書`id`を非修飾形式にする。
連合では両者を修飾形式にする。同じ内容のContextでも連合化の前後でDigestは一致しない。

### 3.1 documents

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

| key | 型 | 内容 |
|---|---|---|
| `id` | string | 文書ID。連合では修飾形式 |
| `workspaceId` | string | 所有workspaceの実効ID |
| `kind` | enum | `requirement`、`technical`、`decision`、`task` |
| `status` | string | Frontmatterの現在状態 |
| `applicability` | enum | `applicable`、`advisory`、`replacement` |
| `frontmatter` | object | §3.1.1の正規化projection |
| `bodyText` | string | §3.1.2の正規化本文 |
| `statements` | object[] | §3.1.3。`id`のcode point辞書順 |
| `strongRelations` | object[] | 強い関係。`relation`、`target`の順でcode point辞書順、重複排除 |

`role`、`projection`、到達距離、到達edge、Bundle内の提示順はdigest inputへ含めない。提示方法の変更で
Digestを変えないためである。

#### 3.1.1 frontmatterのprojection

Core既知fieldだけを上記の固定keyで保持する。値の規則は次とする。

- `id`は連合正規形式、`title`と`status`は原文の正規化string。
- `relations`は5つのCore語彙keyをすべて置き、未宣言は空配列とする。targetは連合正規形式へ展開し、
  重複排除しcode point辞書順に並べる。
- `implements`と`changes`は宣言pathをworkspace root相対の`/` separatorへ正規化し、重複排除して辞書順に並べる。
- `tests`は`path`、`covers`、`command`だけを持つobjectとし、`covers`を修飾形式・辞書順、`command`未宣言をnull、
  要素全体を`path`のcode point辞書順に並べる。
- `verify`と`changes`は非該当種別でもkeyを置き、値をnullまたは空配列とする。
- `x-`拡張fieldは含めない。Coreはこれを合否、Context、command、権限へ使用しないため、
  Contextの同一性判定にも使用しない。
- 未知fieldと`profiles`は含めない。

#### 3.1.2 bodyText

`bodyText`はFrontmatterの終端区切り行の直後から文書末尾までを次の順で正規化したstringとする。

1. BOMを除去する。
2. CRLFとCRをLFへ変換する。
3. 各行の行末の空白類（SPとTAB）を除去する。
4. 先頭と末尾の空行を除去する。
5. 末尾へLFを1つ置く。空本文は空stringとする。

Core 1.0は散文の意味変更と体裁変更を区別しない。上記以外の空行数、見出し記法、表の桁揃え、語順は
すべてDigestへ影響する。過剰にstaleとする方向は安全側であり、変更を見落とす方向は安全側ではない。
除外sectionは設けない。Core 1.0は`Revision History`を要求しないため、追記だけを意味集合の外に置く例外も設けない。

#### 3.1.3 statements

Semantic IRから次のkeyだけを保持する。

```json
{
  "id": "platform::REQ-001:AC-01",
  "actor": "AuthService",
  "activation": {"kind": "WHEN", "text": "有効な認証情報を受信した場合"},
  "modality": "MUST",
  "operation": {"kind": "THEN", "text": "access tokenを1件発行する"},
  "extensions": [
    {"namespace": "quality", "term": "THRESHOLD", "value": "<=200ms"}
  ]
}
```

`documentId`、`localId`、`source`、`raw`、`untrustedText`、`unknownExtensions`は含めない。文書IDは`id`から、
source位置は`bodyText`から導けるためである。`extensions`は`namespace`、`term`の順でcode point辞書順に並べ、
`value`未指定はnullとする。opaque extensionの保持有無はCore解析結果を変えないが、Digestの材料には含める。

`documents[].statements`はContextが収録する対象statementではなく、当該文書が所有する全規範文とする。
対象statementの選択はcoverageとConstraint Ledgerが保持し、Digestの材料にしない。

### 3.2 crossWorkspaceEdges

[モノレポSPEC連合仕様 §6](../02_SPECモデル/05_モノレポSPEC連合仕様.md#6-横断索引とcontext)の
`resolution.crossWorkspaceEdges`と同じ内容、同じ順序、同じ重複排除規則を使う。
単一workspaceでは空配列とする。

### 3.3 settings

context仕様 §6のallowlistだけをkey固定のobjectとして保持する。

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

- `workspaces`は到達workspaceだけを`id`辞書順に並べる。
- `context`はrequest workspaceの既定値適用後の値だけとする。
- `verifyTimeouts`はbindingを1件以上収録したworkspaceだけを`workspaceId`辞書順に並べ、既定値を適用する。
- `commands`はBundleが参照するcommandだけを`workspaceId`、`name`の順で辞書順に並べる。`argv`は
  `{tests}`を展開しないtemplateのまま保持し、`cwd`は未指定時`.`とする。
- `monorepo.maxMembers`、`safety`、未到達workspaceの設定、未使用command、CLI timeout cap、
  出力形式、`--report`は含めない。

## 4. 文字正規化

serialize前に、digest input中の全stringのkeyと値へ次を適用する。

1. Unicode NFCへ正規化する。
2. LFを唯一の改行とする。§3.1.2で正規化済みの`bodyText`を再変換しない。
3. path separatorを`/`とする。
4. 制御文字を除去または置換しない。原文の値を保持する。

比較のための正規化であり、正本fileを書き換えない。

## 5. serializationとhash

serializationはRFC 8785 JSON Canonicalization Schemeに従う。実装は同等の結果を返す限り
自前実装でもよいが、次を満たさなければならない。

- 出力はUTF-8とし、BOM、改行、余分な空白を含めない。
- object keyはUTF-16 code unitの昇順に並べる。
- 数値はJSON数値のうち安全な整数だけを使う。Core 1.0のdigest inputは非整数、指数表記、
  `-0`、`NaN`、`Infinity`を持たない。
- stringのescapeはRFC 8785が要求する最小集合だけとする。
- 配列は§3で規定した順序を保持し、serializerが並べ替えない。
- 省略可能なkeyを作らない。値がない場合はnullまたは空配列を明示する。

hashはSHA-256とし、上記UTF-8 byte列だけを入力とする。結果は小文字16進64桁とし、
`sha256:`を前置する。大文字16進、他のhash、切詰めを使わない。

## 6. 適合

適合実装は次を満たす。

- 同じ入力treeと同じ実効設定に対し、実行順、cacheの有無、file system上のpath、locale、
  process環境に依存せず同じDigestを返す。
- `--detail`、`--expand`、`--format`、`--report`、CLI timeout capの変更でDigestを変えない。
- 設定の構文、型、必須field、参照commandが不適合な場合はDigestを計算せず、
  不完全な材料からDigestを作らない。
- `digestVersion`、`resolverVersion`、材料の意味を変更する場合はCore majorまたはminorを上げ、
  過去のDigest値を同じversionで再定義しない。

適合fixtureは、固定入力に対する期待Digest値を`expected/context.json`へ含める。
fixtureの配置と比較方法は[適合fixture仕様](04_適合fixture仕様.md)に従う。
