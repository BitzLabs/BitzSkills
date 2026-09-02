# `bitz context`仕様 1.0

## 1. 目的

起点SPECまたはEARS-AI statementから、解釈・実装・検証に必要な文書を型付き関係で完全解決し、
目的別Context Bundleを返す。依存の完全解決とLLMへの提示量を分離する。

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

purpose既定値は`interpret`、detail既定値は`standard`とする。起点は文書IDとstatement IDだけを受け付け、
path、code、testを受け付けない。単一workspaceでは非修飾IDだけを受け付ける。連合ではactive workspaceの
非修飾IDまたは修飾IDを受け付け、全起点の所有workspaceを1つに限定する。`--workspace`は非修飾IDの解決基準を
明示し、起点所有者と一致しなければならない。`--all-workspaces`は提供しない。複数起点は重複排除して
連合正規ID辞書順に正規化する。

`expand`は完全解決集合にある文書だけを`full`提示へ昇格する。集合外IDは`CTX-PROJECTION-001`／failedとし、
暗黙に依存へ追加しない。連合では非修飾`expand`をrequest workspaceから、修飾`expand`を連合索引から解決する。

## 3. 処理

1. request workspace、連合catalog、workspace設定を解決する。
2. 単一workspaceまたは連合catalog内の全SPECから軽量索引を構築する。
3. ID、型、状態、強い関係、循環を検査する。
4. [purpose別閉包](../02_SPECモデル/04_関係・トレースモデル.md#6-purpose別の閉包)を完全解決する。
5. Context上限を検査する。
6. 文書をroleへ分類し、Constraint Ledgerとcoverageを生成する。
7. Context Digestを計算する。
8. detailとexpandに応じた提示を生成する。
9. `--expect-digest`があれば現在Digestと比較する。

強い関係の一部を解決できない場合、部分Bundleを成功結果として返さない。

## 4. Context Bundle

```json
{
  "schemaVersion": "1.0",
  "operation": "context",
  "status": "passed_with_warnings",
  "purpose": "implement",
  "workspace": {"id": "root", "path": "."},
  "roots": ["REQ-001"],
  "contextDigest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "revision": {"commit": "0123456789abcdef", "dirty": false},
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
      "statementRefs": ["REQ-001:AC-01"],
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

`resolution.complete: true`は型、状態、循環、上限を含む完全解決が成立したことを示す。
`constraintLedger`はapplicable文書の対象statementをSemantic IRの意味fieldで1回だけ保持する。
連合ではtop-level `workspace`をrequest workspaceとし、`roots`、文書`id`、statement参照を修飾形式で返す。
各`documents[]`は`workspaceId`を持ち、`path`はそのworkspace root相対とする。
`resolution.workspaces`と`resolution.crossWorkspaceEdges`のfield、内容、順序は
[モノレポSPEC連合仕様](../02_SPECモデル/05_モノレポSPEC連合仕様.md)に従い、連合結果では必須とする。

## 5. Projection

| projection | 内容 |
|---|---|
| `full` | 正規化Frontmatter、現行本文、statement参照、到達理由 |
| `normative` | 識別情報、statement参照、到達理由。非規範本文は省略 |
| `reference` | ID、種別、状態、role、path、到達理由、展開可否 |

`standard`は起点、TASK、replacement、距離1文書をfull、間接constraint/refinementをnormative、advisoryを
referenceとする。`compact`は原文を省略してManifest、Diagnostic、Ledger、coverage、境界、参照を返す。
`full`は全解決文書をfull提示する。

どのdetailでも完全解決、全対象`MUST`、Constraint Ledgerを省略しない。提示方法の変更はContext Digestを
変えない。Core 1.0はProjection Digestを返さない。

## 6. Context Digest

Context Digestは次をCanonical JSON化したSHA-256である。形式は`sha256:[0-9a-f]{64}`とする。

- SPEC Schema、EARS-AI、Context Resolverのversion
- purpose、request workspace IDと起点の連合正規ID
- 閉包内文書のID、種別、状態、適用区分、正規化Frontmatter、現行本文の意味内容
- 強い関係
- EARS-AI Semantic IRのCanonical意味field
- `implements`、test対応、command名、argv template、cwd、設定timeout、TASK `changes`
- Contextに影響する実効設定
- 到達workspaceのID、repository root相対path、修飾edge

次は含めない。

- 生成時刻、絶対path、cache位置、出力形式
- detail、expand、各文書projection、実際の提示内容
- Git/PR/ADRにある変更履歴
- code/test fileの内容
- CLI timeout cap
- 未到達workspaceの設定、本文、catalog列挙順

公開するhashはContext Digestだけとする。文書単位hashと提示内容digestは内部実装に限定する。

## 7. stale検出

adapterは最初の書込み直前と、仕様・設定変更を認識した再開時に同じrequestを`--expect-digest`付きで再実行する。
一致しなければ`CTX-STALE-001`／blockedとし、新しい仕様を暗黙受諾しない。

## 8. 上限

既定20文書、128 KiB、hard limit 100文書、1 MiBとする。意味依存にdepth上限を設けない。
完全閉包が上限を超えれば`CTX-LIMIT-001`／blockedとする。detail/expandだけで提示hard limitを超えれば
`CTX-PROJECTION-LIMIT-001`／failedとする。

## 9. Markdown表示順

```text
Bundle Manifest
Diagnostics and Coverage Gaps
Normative Constraint Ledger
Root Intent
Required Context
Applicable Refinements
Replacement Candidates
Work Boundary
Verification Bindings
Advisory Documents
```

adapter命令はBundle外から与え、本文をsystem instructionへ昇格しない。

## 10. Diagnostic

| code | result | 条件 |
|---|---|---|
| `CTX-ROOT-MISSING-001` | failed | 起点ID不在 |
| `CTX-RELATION-TYPE-001` | failed | relation型不正 |
| `CTX-RELATION-MISSING-001` | failed | strong target不在 |
| `CTX-CYCLE-001` | failed | 禁止循環 |
| `CTX-TASK-DEPENDENCY-001` | blocked | 先行TASK未完了 |
| `CTX-STATE-001` | blocked | purposeに適用不能 |
| `CTX-STATE-SUPERSEDED-001` | blocked | 起点・依存先が置換済み |
| `CTX-STATE-SUPERSEDED-002` | failed | 有効後継が複数 |
| `CTX-LIMIT-001` | blocked | 完全閉包が上限超過 |
| `CTX-COVERAGE-TASK-001` | passed_with_warnings | implement対象MUSTが未addressed |
| `CTX-COVERAGE-TEST-001` | warning／blocked | implementではwarning、verifyではblocked |
| `CTX-STALE-001` | blocked | expected Digest不一致 |
| `CTX-PROJECTION-001` | failed | expand対象が解決集合外 |
| `CTX-PROJECTION-LIMIT-001` | failed | 提示量hard limit超過 |

## 11. adapter契約

adapterは実装前にimplement Bundleを取得し、operation statusが`passed`または`passed_with_warnings`で、
`resolution.complete: true`である場合だけ書込みを開始する。`failed`、`blocked`、`error`、引数不正では停止する。
全`MUST`、constraint、work boundary、coverage gapを計画へ反映し、reference内容を推測しない。
実装後はcheckを実行し、完了前にverify Bundleを再解決してverifyを呼ぶ。checkとverifyも通過statusの場合だけ
次段階へ進める。
