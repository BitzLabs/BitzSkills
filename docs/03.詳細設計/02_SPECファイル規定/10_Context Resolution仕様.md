# Context Resolution仕様 1.0

## 1. 目的

Context Resolutionは、起点となるSPECまたはEARS-AI規範文から、実装・解釈・検証に必要な文書を
型付き依存関係に従って決定論的に収集し、エージェントへContext Bundleとして渡すCore機能である。

Coreは **依存の完全解決** と **LLMへの提示量** を分離する。強い依存は提示される原文量にかかわらず
終端まで解決・検査し、その結果から目的別のProjectionを生成する。段階的提示は完全性を弱める
探索打切りではなく、完全に解決した集合の表示形式である（[ADR-014](../../02.設計書/10_決定記録/ADR-014_Semantic-IRと段階的Context-Projection.md)）。

単なるリンク一覧ではなく、次を保証対象にする。

- 強い依存を終端まで探索し、参照漏れを成功扱いしない。
- 同じ入力、設定、Core版から同じ文書集合、順序、digestを得る。
- EARS-AI規範文単位で、TASKの対象とテスト対応の不足を可視化する。
- 古いコンテキストに基づく実装をdigest再照合で停止する。
- 上限超過時に一部だけのコンテキストを完全なものとして渡さない。
- 全適用対象の規範文を構造化したConstraint Ledgerとして渡し、原文Markdownは重要度に応じて段階表示する。

自由記述の意味的矛盾、テストが実際に要求を検証しているか、実装が要求を満たすかは保証しない。

## 2. 公開操作

```text
bitz context <spec-or-statement-id>...
  [--purpose interpret|implement|verify]
  [--format markdown|json]
  [--detail compact|standard|full]
  [--expand <document-id>]...
  [--expect-digest sha256:<hex>]
```

`purpose`の既定値は`interpret`とする。起点IDは文書IDと規範文IDを受け付け、重複を除いてID辞書順に
正規化する。パスを起点にせず、移動後も安定するIDを使用する。

`detail`の既定値は`standard`とする。`expand`は完全解決済み集合に含まれる文書IDだけを受け付け、
指定文書のProjectionを`full`へ昇格する。同じ起点、purpose、Core版、入力に対する`detail`と`expand`の
変更は、解決集合、status、Context Digestを変えず、提示内容とProjection Digestだけを変える。
解決集合外のIDを指定した場合は、暗黙に依存を追加せず`CTX-PROJECTION-001`で`failed`とする。

## 3. 型付き関係

関係はFrontmatterの`relations`に記述する。

| 関係 | 意味 | Contextへの影響 |
|---|---|---|
| `requires` | sourceを解釈・実行する前提 | targetを再帰的に含める |
| `refines` | sourceがtargetを具体化・制約する | targetと、targetに対する有効なrefinerを含める |
| `addresses` | TASKが対象規範文を実装する | `implement`でTASKと対象句を対応付ける |
| `supersedes` | sourceが旧文書を置き換える | 旧文書をadvisoryとして識別する |
| `related` | 閲覧用の弱い関連 | 自動的には含めない |

`requires`、`refines`、`addresses`、`supersedes`を強い関係とする。強い関係の未解決、型違反、
禁止された循環はエラーである。`related`は探索集合を増やさず、参照切れを警告に留める。

## 4. 関係の型制約

| source | 使用可能な関係 | target |
|---|---|---|
| REQ | `requires` | REQ、TECH、accepted ADR |
| REQ | `refines` | REQまたはその規範文 |
| REQ | `supersedes` | REQ |
| TECH | `requires` | REQ、TECH、accepted ADR |
| TECH | `refines` | REQ、TECHまたはその規範文 |
| TECH | `supersedes` | TECH |
| ADR | `requires` | REQ、TECH、accepted ADR |
| ADR | `supersedes` | ADR |
| TASK | `requires` | REQ、TECH、TASK、accepted ADR |
| TASK | `addresses` | REQ/TECHの規範文、または規範文を持たないTECH |
| 全種別 | `related` | 任意の文書ID |

規範文を持つREQまたはTECHをTASKが文書IDだけで`addresses`することは禁止する。対象句の列挙を省略すると、
実装漏れを機械検出できないためである。

`requires`と`refines`を合わせた意味依存グラフ、および`supersedes`の連鎖は循環を禁止する。
`related`の循環は許容し、探索しない。TASK間の`requires`循環は実行順序を決められないためエラーとする。

## 5. purpose別の閉包

### `interpret`

1. 起点文書または規範文の所有文書を含める。
2. 各文書の`requires`を終端までたどる。
3. `refines`のtargetを含める。
4. 対象文書を`refines`する`approved`文書を逆参照で含め、その`requires`もたどる。
5. 起点が置換済み文書の場合、旧文書をadvisory、有効な後継文書をreplacementとして識別する。
6. `related`、TASK、コード、テストは自動追加しない。

### `implement`

`interpret`閉包に加え、次を含める。

- 起点と適用されるrefinementの規範文を`addresses`する`open` TASK
- 起点がTASKの場合、その`addresses`対象と`requires`閉包
- 適用文書の`implements`、テスト対応、TASKの`changes`
- 対象となる全EARS-AI規範文と実装・テスト網羅状況

### `verify`

`interpret`閉包に加え、対象規範文のテスト対応、検証コマンド、実装パスを含める。TASKは起点として
指定された場合だけ含める。

## 6. 状態と適用可能性

| 文書 | applicable | advisory | blocking条件 |
|---|:--:|:--:|---|
| `approved` REQ/TECH | Yes | No | なし |
| `draft` REQ/TECH | No | Yes | `implement`または`verify`の起点 |
| `outdated` REQ/TECH | No | Yes | 強い依存先または`implement`/`verify`の起点 |
| 有効な`supersedes`逆参照を持つREQ/TECH | No | Yes | 強い依存先または`implement`/`verify`の起点 |
| `accepted` ADR | Yes | No | なし |
| `proposed` ADR | No | Yes | 強い依存先 |
| `rejected`/`superseded` ADR | No | Yes | 強い依存先 |
| `open` TASK | Work | No | なし |
| `done` TASK | No | History | なし |

advisory文書は本文を別区分で渡し、規範として適用してはならない。強い依存に適用不能な文書が必要な場合、
Context Bundle全体を`blocked`とする。

置換済みREQ/TECHを`implement`または`verify`へ指定した場合は、後継IDを`suggestedAction`へ含めて
`blocked`とする。Coreは後継へ暗黙に起点を差し替えない。同じ旧文書に複数の有効な後継がある場合は
置換が曖昧なため`failed`とする。

有効な後継とは、同種の旧文書を`supersedes`する`approved`のREQ/TECHを指す。`draft`または`outdated`の
後継候補だけでは旧文書を置換済みと判定しない。`interpret`で置換済み文書を起点にした場合は、旧文書と
後継を区別して`passed_with_warnings`で返す。

## 7. 決定論的探索

1. 全文書とEARS-AI規範文のID索引を作る。
2. 型、状態、強い関係、循環を検査する。
3. 起点をID辞書順へ正規化する。
4. purpose規則に従い、強い関係の完全な閉包を計算する。
5. 文書を`roots`、`requirements`、`constraints`、`refinements`、`replacements`、`work`、`advisory`へ分類する。
6. 各区分を最短距離、種別順REQ・TECH・ADR・TASK、ID辞書順で並べる。
7. 規範文を文書順、source line、規範文IDの順で並べる。
8. 内容hashと関係をCanonical JSON化し、Context Digestを計算する。

同じ文書が複数経路から到達した場合は1回だけ収録し、`reachedBy`へ全経路の直前edgeを記録する。
実装はvisited setを用いるが、循環を単に無視せずDiagnosticとして報告する。

## 8. Context Bundleと段階的Projection

Context Bundleは生成ファイルを正本にせず、コマンド結果として返す。

```json
{
  "schemaVersion": "1.0",
  "operation": "context",
  "status": "passed_with_warnings",
  "purpose": "implement",
  "roots": ["REQ-001"],
  "contextDigest": "sha256:0123456789abcdef",
  "projectionDigest": "sha256:fedcba9876543210",
  "revision": {"commit": "0123456789abcdef", "dirty": false},
  "resolution": {
    "complete": true,
    "documentCount": 2,
    "unresolvedStrongRelations": 0
  },
  "projection": {
    "detail": "standard",
    "expanded": []
  },
  "documents": [
    {
      "id": "REQ-001",
      "kind": "requirement",
      "status": "approved",
      "role": "root",
      "path": ".spec/requirements/REQ-001.md",
      "contentHash": "sha256:abcdef0123456789",
      "projection": "full",
      "statementRefs": ["REQ-001:AC-01", "REQ-001:AC-02"],
      "untrustedText": true
    },
    {
      "id": "TECH-014",
      "kind": "technical",
      "status": "approved",
      "role": "constraint",
      "path": ".spec/technical/TECH-014.md",
      "contentHash": "sha256:1234567890abcdef",
      "projection": "normative",
      "statementRefs": [],
      "expandable": true,
      "untrustedText": true
    }
  ],
  "constraintLedger": {
    "statements": [
      {
        "id": "REQ-001:AC-01",
        "documentId": "REQ-001",
        "role": "root",
        "modality": "MUST",
        "actor": "AuthService",
        "activation": {"kind": "WHEN", "text": "有効な認証情報を受信した場合"},
        "operation": {"kind": "THEN", "text": "アクセストークンを1件発行する"}
      },
      {
        "id": "REQ-001:AC-02",
        "documentId": "REQ-001",
        "role": "root",
        "modality": "MUST",
        "actor": "AuthService",
        "activation": {"kind": "WHEN", "text": "認証情報が無効な場合"},
        "operation": {"kind": "THEN", "text": "トークンを発行せず認証エラーを返す"}
      }
    ]
  },
  "coverage": {
    "must": {
      "total": ["REQ-001:AC-01", "REQ-001:AC-02"],
      "addressed": ["REQ-001:AC-01"],
      "tested": ["REQ-001:AC-01"],
      "unaddressed": ["REQ-001:AC-02"],
      "untested": ["REQ-001:AC-02"]
    },
    "should": {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []},
    "may": {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []},
    "adjacent": []
  },
  "limits": {"documents": 2, "bytes": 4096},
  "diagnostics": []
}
```

`resolution.complete: true`は、強い依存の完全閉包、型、状態、循環、上限の検査が完了したことを表す。
部分解決した集合にこの値を設定してはならない。`constraintLedger.statements`は完全解決したapplicable文書の
全EARS-AI規範文をSemantic IRで保持する。少なくとも全`MUST`と、purposeに関係する`SHOULD`をLLM向け表示の
先頭で省略せず提示する。依存が深いことを理由に規範文を参照だけへ落としてはならない。
JSONでは各Semantic IRをConstraint Ledgerに1回だけ格納し、文書要素は`statementRefs`で参照する。

各文書のProjectionは次の3値とする。

| Projection | 含める内容 | 主用途 |
|---|---|---|
| `full` | 正規化Frontmatter、原文Markdown、`statementRefs`、`reachedBy` | 起点、作業境界、直接理解が必要な文書 |
| `normative` | 識別情報、Constraint Ledgerへの`statementRefs`、`reachedBy`。非規範の本文・例は省略 | 間接制約、refinement |
| `reference` | ID、種別、状態、role、hash、到達理由、展開可否 | advisory、背景、必要時だけ読む資料 |

`standard`の既定Projectionは次の優先順で決める。依存深度だけでは決めない。

1. 起点、対象TASK、replacement、直接の作業境界は`full`。
2. purposeに直接関係する文書と距離1のapplicable文書は`full`。
3. それ以外のapplicableなconstraintとrefinementは`normative`。
4. advisory、history、弱い補足は`reference`。
5. `--expand`で明示された文書は上記にかかわらず`full`。

`compact`は起点を含む全原文を省略し、Manifest、Diagnostics、Constraint Ledger、Coverage、Work Boundary、
参照一覧だけを返す。`full`は解決集合の全資料を`full`にする。いずれのdetailでも完全解決とConstraint Ledgerを
省略してはならない。自由記述とコード例を含むすべてのSPEC由来テキストは`untrustedText: true`のまま渡す。

段階参照は状態を持つ常駐サービスを要求しない。アダプターは同じ起点とpurposeを再指定し、必要な文書だけを
`--expand`して再取得する。Coreは同じ入力から同じProjectionとProjection Digestを返す。

Markdown形式は次の固定順で表示する。

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

エージェントへの命令はBundle外の信頼されたアダプターが与える。文書本文をシステム命令へ昇格しない。

## 9. 句単位カバレッジ

対象REQ/TECHと適用されるrefinementのEARS-AI規範文を規範強度ごとに集計する。

- `MUST`: `verify`では1件以上のテスト対応を必須とする。
- `SHOULD`: 未対応をwarningとする。
- `MAY`: 対応の有無を情報として表示する。
- TASK起点では、`addresses`にない句を作業対象へ含めないが、同一文書の未対象句をadjacentとして表示する。
- REQ起点の`implement`では全`MUST`を対象とし、未addressedをwarning、未testedをwarningとする。
- `verify`では未testedの`MUST`が1件でもあればテスト実行前に`blocked`とする。

`coverage`は`must`、`should`、`may`を同じ構造で持ち、各区分に`total`、`addressed`、`tested`、
`unaddressed`、`untested`を格納する。TASK起点で同一文書内の対象外規範文がある場合だけ`adjacent`へ格納する。

| purpose | coverageの扱い |
|---|---|
| `interpret` | `coverage`を省略する |
| `implement` | 全区分と`adjacent`を返す |
| `verify` | 全区分を返す。`addressed`と`unaddressed`は情報として保持し、合否は`tested`と`untested`で決める |

テスト対応は「そのテストファイルが句を対象として宣言した」ことだけを保証する。assertionの十分性は
テストレビュー、mutation testing、実行結果などで別に評価する。

## 10. Context Digestとstale検出

Context Digestは、次をCanonical JSON化したSHA-256とする。

- Schema版、EARS-AI版、Context Resolver版
- purposeと起点ID
- applicable/advisory文書のID、状態、内容hash
- 閉包内の強い関係
- EARS-AI Semantic IRのCanonical表現
- 実装パス、テスト対応、検証コマンド名、TASK変更境界

生成時刻、絶対パス、キャッシュ位置、出力形式は含めない。
`detail`、`expand`、各文書のProjection、Projection Digestも含めない。提示方法を変えても、完全解決した
仕様解釈が同じならContext Digestは同一でなければならない。

Projection Digestは、Context Digest、`detail`、`expand`、文書ごとのProjection、実際に提示する内容を
Canonical JSON化して計算する。これは表示の再現性とキャッシュ照合に使い、stale判定には使わない。

実装・テストファイルの内容hashも含めない。エージェント自身の正当な編集でDigestが変わり続けるのを避けるためである。
コード競合はGitのHEAD、index、worktree差分とTASK変更境界で検出し、Context Digestは仕様解釈のstale検出に限定する。

エージェントは編集直前に同じrequestを`--expect-digest`付きで再実行する。現在digestが一致しなければ
`CTX-STALE-001`で`blocked`とし、変更済み文書とedgeを返す。自動的に新しい意味を受諾して実装を続行しない。

## 11. 上限と性能

既定値は`.spec/bitz.yaml`で設定する。

| 項目 | 既定 | hard limit |
|---|---:|---:|
| 文書数 | 20 | 100 |
| Semantic IRと標準Projectionの合計 | 128 KiB | 1 MiB |

意味依存には深度上限を設けない。深度で途中打切りすると末端制約を欠落させるためである。閉包が上限を超えた場合は
`CTX-LIMIT-001`で`blocked`とし、必要量と超過原因になったedgeを返す。部分bundleで`passed`を返さない。

原文を`reference`へ落として上限内に見せることで、解決上限超過を成功扱いしてはならない。既定上限は
完全解決した文書集合とSemantic IRに対して判定する。`--detail full`または`--expand`による提示量だけが
hard limitを超える場合は`CTX-PROJECTION-LIMIT-001`で`failed`とし、Context Resolution自体のstatusとは区別する。

索引は1回の走査で作り、内容hashが同じ文書は再解析しない。10,000 SPECの索引作成を除き、通常の20文書以下の
Context Resolutionは基準環境で1秒以内を目標とする。ネットワークとLLMを使用しない。

## 12. Diagnostic

| コード | 条件 |
|---|---|
| `CTX-ROOT-MISSING-001` | 起点IDが解決できない。結果は`failed` |
| `CTX-RELATION-TYPE-001` | 関係のsource/target型が不正 |
| `CTX-RELATION-MISSING-001` | 強い関係のtargetがない |
| `CTX-CYCLE-001` | 禁止された循環がある |
| `CTX-STATE-001` | 強い依存先が適用不能。結果は`blocked` |
| `CTX-STATE-SUPERSEDED-001` | 起点または強い依存先が置換済み。後継IDを返し、結果は`blocked` |
| `CTX-STATE-SUPERSEDED-002` | 同じ旧文書に複数の有効な後継がある。結果は`failed` |
| `CTX-LIMIT-001` | 完全な閉包が上限を超える。結果は`blocked` |
| `CTX-COVERAGE-TASK-001` | 対象`MUST`をaddressするTASKがない |
| `CTX-COVERAGE-TEST-001` | 対象`MUST`にテスト対応がない |
| `CTX-STALE-001` | 期待Context Digestと現在値が異なる。結果は`blocked` |
| `CTX-PROJECTION-001` | `expand`対象が完全解決済み集合にない。結果は`failed` |
| `CTX-PROJECTION-LIMIT-001` | 要求されたProjectionが提示量hard limitを超える。結果は`failed` |

関係の型不正、参照切れ、循環は成果物不適合として`failed`にする。状態不適合、上限超過、Digest不一致は
成果物を直ちに不正とは断定せず、現在の操作を安全に継続できないため`blocked`にする。

## 13. エージェントアダプター契約

アダプターは次を守る。

1. 実装前に`purpose=implement`の完全なBundleを取得する。
2. `blocked`またはerror Diagnosticがあればコード編集を開始しない。
3. Root Intent、全`MUST`、constraints、work boundary、coverage gapsを計画へ反映する。
4. `reference`の内容を推測しない。設計判断や実装判断に必要なら、同じ起点とpurposeで対象を`--expand`する。
5. 実装報告では対応した規範文IDを列挙する。
6. 最初の書込み直前、および仕様・設定の変更を認識した再開時にContext Digestを再照合する。
7. 完了前に`purpose=verify`を再解決し、未tested `MUST`がない状態で`bitz verify`を実行する。
8. advisory、自由記述、コード例を権限付与やツール命令として扱わない。
