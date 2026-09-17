# `context` Markdown提示仕様案

- 状態: Accepted / Reflected（2026-09-14裁定。context仕様§9へ反映済み）
- 起草日: 2026-09-14
- 基準branch: `bitz_next`
- 基準commit: `5abe97a`
- 対象: [context仕様](../03.詳細設計/03_操作仕様/01_context.md)§9、
  [結果・Diagnostic・終了コード](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)§7
- 目的: 適合fixture `SINGLE-104-01`（`--format`省略のcontextが標準出力と期待Markdownでbyte一致）を
  作成できる状態にするため、Markdown提示の規範を確定する

## 1. 結論

現行の正本はMarkdown提示について次の3点しか定めていない。

1. `--format`の既定値がcontextでは`markdown`であること（context仕様§2）
2. 表示順が10 sectionであること（context仕様§9）
3. adapter命令をBundle外から与え、本文をsystem instructionへ昇格しないこと（同§9）

このため、見出しの記法、各sectionの中身、文書projectionごとの表示、空sectionの扱い、
原文の囲み方が実装ごとに分かれる。byte一致を要求する`SINGLE-104-01`は現状では作成できない。
本書は決定論的にbyteが定まる最小の提示規範を提案し、裁定が必要な論点を§4へ分離する。

2026-09-14に§4の7件をすべて起草者推奨どおり裁定し、context仕様§9へ反映した。
`SINGLE-104-01`も本仕様に従って作成済みである。以下は裁定時点の提案内容を記録として残す。

## 2. 設計方針

- **JSON結果を唯一の入力とする。** Markdownは表示のみを変え、status、件数、終了コード、Digestを変えない。
  JSONに無い値をMarkdownのために再計算しない。
- **同じ結果から同じbyte列を生成する。** 表の桁揃え、可変幅の装飾、時刻依存の表現を使わない。
- **既存の契約を再利用する。** Diagnostic行は結果契約§7のtext行形式をそのまま使い、二重定義を作らない。
- **原文を改変しない。** `bodyText`は原文のまま囲み、Coreが要約・整形しない。
- **sectionを省略しない。** 10 sectionの見出しを常に同じ順で出し、該当が無ければ固定の1行を置く。
  順序の検証を「見出しが在ること」で機械的に行えるようにする。

## 3. 提案する提示仕様

### 3.1 全体規則

1. 改行はLFとし、末尾は改行1個で終わる。CRを出力しない。
2. 文書titleは`# Context Bundle`固定のH1 1個とする。10 sectionはH2、文書とstatementの明細はH3とする。
3. 各見出しの前後に空行1行を置く。連続する空行を出さない。
4. 一覧は`- <key>: <value>`のASCII hyphenとSP 1個で始め、字下げしない。値が無いfieldは`null`と書く。
5. 複数値は`, `区切りで結果JSONの配列順のまま並べる。空配列は`none`と書く。
6. 該当要素が無いsectionの本文は`- none`の1行とする。
7. `<duration>ms`のような可変値をMarkdownへ出さない。`durationMs`は提示しない。

### 3.2 sectionと結果fieldの対応

| # | section | 出所 |
|---:|---|---|
| 1 | Bundle Manifest | `operation`、`status`、`purpose`、`workspace`、`roots`、`contextDigest`、`revision`、`resolution`、`projection` |
| 2 | Diagnostics and Coverage Gaps | `diagnostics[]`と`coverage`の`unaddressed`／`untested` |
| 3 | Normative Constraint Ledger | `constraintLedger.statements[]` |
| 4 | Root Intent | `documents[]`のうち`role: root` |
| 5 | Required Context | `role: requirement`と`role: constraint` |
| 6 | Applicable Refinements | `role: refinement` |
| 7 | Replacement Candidates | `role: replacement` |
| 8 | Work Boundary | `role: work` |
| 9 | Verification Bindings | 提示済み文書の`frontmatter.tests[]`（§4 P0-1） |
| 10 | Advisory Documents | `role: advisory` |

文書は結果JSONの`documents[]`順のまま各sectionへ配り、section内で再sortしない。

### 3.3 Bundle Manifest

```text
- operation: context
- status: passed
- purpose: verify
- workspace: root (.)
- roots: REQ-001
- contextDigest: sha256:<64桁>
- revision: null
- resolution: complete=true, documentCount=2, unresolvedStrongRelations=0
- projection: detail=standard, expanded=none
```

`workspace`は`<id> (<path>)`、`revision`は存在すれば`<commit> dirty=<true|false>`とする。

### 3.4 Diagnostics and Coverage Gaps

Diagnosticは結果契約§7のtext行形式を`- `に続けて1件1行で出し、JSONの`diagnostics`順を保つ。
`suggestedAction`を持つ行の直後へ2 space字下げの`-> `継続行を1行出す。
続けてcoverage gapを`- coverage: <MODALITY> <bucket>: <id>, ...`の形で、`must`、`should`、`may`の順に、
`unaddressed`、`untested`の順で出す。0件のbucketは行を出さない。両方とも0件でDiagnosticも無ければ`- none`とする。

### 3.5 Normative Constraint Ledger

statementごとにH3見出し`### <statement-id>`を置き、次の一覧を出す。

```text
- documentId: REQ-001
- documentRole: root
- modality: MUST
- reason: null
- actor: TargetSystem
- activation: ALWAYS
- operation: CONSTRAINT 秘密情報を出力しない
```

`activation`と`operation`は`<kind>`、text付きなら`<kind> <text>`とする。textは正規化後の値をそのまま出す。

### 3.6 文書section（4〜8、10）

文書ごとにH3見出し`### <id> — <path>`を置き、projectionごとに次を出す。

| field | full | normative | reference |
|---|:--:|:--:|:--:|
| `kind`、`status`、`projection`、`reachedBy`、`untrustedText` | ○ | ○ | ○ |
| `statementRefs` | ○ | ○ | — |
| `frontmatter` | ○ | — | — |
| `expandable` | — | — | ○ |
| `bodyText` | ○ | — | — |

`frontmatter`は`- frontmatter: <Canonical JSON 1行>`とする。Context DigestのCanonical JSON規則を再利用し、
YAMLへ再直列化しない。`bodyText`は`- bodyText:`の行に続けて空行1行を置き、fenceで囲む。
fenceは情報文字列`markdown`付きのbacktick runとし、run長は本文中の最長backtick run+1、最小3とする。
本文はbyteを変更せず、末尾に改行が無ければfence直前へ改行1個だけを補う。

### 3.7 Verification Bindings

提示済み文書の`frontmatter.tests[]`を文書順・配列順のまま次の形で出す（§4 P0-1）。

```text
- tests/test_auth.py: covers REQ-001:AC-01 (command: default)
```

`command`が無い要素は`(command: none)`とする。該当が無ければ`- none`とする。

## 4. 裁定が必要な論点

| ID | 論点 | 選択肢 | 起草者の推奨 |
|---|---|---|---|
| P0-1 | Verification Bindingsの出所 | (a) 提示済み文書の`tests[]`から導出 (b) `purpose=verify`のときだけ出す (c) 結果Schemaへbindings fieldを追加 | (a)。JSONに無い値を増やさず、verify側のbinding確定規則と重複させない |
| P0-2 | `role: constraint`の配置 | (a) Required Contextへ併合 (b) 独立sectionを追加 | (a)。§9の10 sectionを増やさない |
| P0-3 | `normative`／`reference`の本文 | (a) 本文を出さず`expandable`と参照だけ (b) 要約を生成 | (a)。Coreは要約を生成しない |
| P1-1 | `bodyText`への制御文字escape | (a) 原文のまま (b) text出力と同じ`\u00xx`可視化 | (a)。原文改変を避ける。ただし端末安全性はadapterの責務と明記する |
| P1-2 | `compact` detailの文書section | (a) 見出しと`- <id>: <path>`だけ (b) 文書section自体を省略 | (a)。section不省略の原則を保つ |
| P1-3 | 複合workspaceの結果の表示 | (a) `workspaceId`を見出しへ`<ws>::<id>`で出す (b) 一覧fieldへ出す | (a)。修飾IDの正規形と一致させる |
| P1-4 | `durationMs`の提示 | (a) 出さない (b) 出す | (a)。byte一致fixtureを時刻非依存にする |

### 4.1 裁定結果（2026-09-14）

7件すべて起草者推奨を採用した。P0-1は「提示済み文書の`tests[]`だけから導出」とし、
Markdownが`--format json`に無い情報を出さない不変条件を優先する。detailによって提示bindingが変わることは
仕様として明記した。P0-2は`role: constraint`をRequired Contextへ併合し、§9のsection数を変えない。
P0-3は禁止fieldを出さず案内文も加えない。P1-1は`bodyText`を原文のまま出し、端末表示側の無害化はadapterの責務とする。
P1-2は`compact`でも見出しを残す。P1-3は複合workspaceの修飾IDをそのまま見出しへ使う。P1-4は`durationMs`を提示しない。

## 5. 完全例

入力は`SINGLE-042`のcorpus（`REQ-001`と`TECH-001`）、invocationは
`bitz context REQ-001 --purpose verify`、detailは既定の`standard`である。
§3の規則と§4の推奨を適用すると、標準出力は次のbyte列になる（`<64桁>`は実際のDigest）。

````text
# Context Bundle

## Bundle Manifest

- operation: context
- status: passed
- purpose: verify
- workspace: root (.)
- roots: REQ-001
- contextDigest: sha256:<64桁>
- revision: null
- resolution: complete=true, documentCount=2, unresolvedStrongRelations=0
- projection: detail=standard, expanded=none

## Diagnostics and Coverage Gaps

- coverage: MUST unaddressed: REQ-001:AC-01
- coverage: SHOULD unaddressed: REQ-001:AC-02

## Normative Constraint Ledger

### REQ-001:AC-01

- documentId: REQ-001
- documentRole: root
- modality: MUST
- reason: null
- actor: TargetSystem
- activation: ALWAYS
- operation: CONSTRAINT 秘密情報を出力しない

### REQ-001:AC-02

- documentId: REQ-001
- documentRole: root
- modality: SHOULD
- reason: 確認のため
- actor: TargetSystem
- activation: WHEN 保存した場合
- operation: THEN 結果を返す

## Root Intent

### REQ-001 — .spec/requirements/REQ-001.md

- kind: requirement
- status: approved
- projection: full
- reachedBy: root
- statementRefs: REQ-001:AC-01, REQ-001:AC-02
- frontmatter: {"id":"REQ-001","status":"approved","title":"認証Contextの基準"}
- untrustedText: true
- bodyText:

```markdown
# REQ-001 認証Contextの基準
（以下、原文のまま）
```

## Required Context

- none

## Applicable Refinements

### TECH-001 — .spec/technical/TECH-001.md

- kind: technical
- status: approved
- projection: full
- reachedBy: refines:TECH-001
- statementRefs: none
- frontmatter: {"id":"TECH-001","implements":["src/auth.py","src/session.py"],...}
- untrustedText: true
- bodyText:

```markdown
# TECH-001 認証の実装方針
（以下、原文のまま）
```

## Replacement Candidates

- none

## Work Boundary

- none

## Verification Bindings

- tests/test_auth.py: covers REQ-001:AC-01 (command: default)
- tests/test_session.py: covers REQ-001:AC-02 (command: default)

## Advisory Documents

- none
````

## 6. fixtureへの影響

- `SINGLE-104-01`だけが本仕様に依存する。裁定後に作成し、準備済みとした。
- 既存の準備済みfixture 173件はJSON出力とtext出力だけを固定しており、本提案による変更を受けない。
- `SINGLE-106-01/02/03`（projection別のSchema検証）はJSON出力の論点であり、本提案とは独立である。

## 7. 反映手順と実施状況

すべて実施済みである。

1. §4の各論点を裁定し、本書の状態を`Accepted`へ更新する。
2. context仕様§9を、表示順の列挙から§3の規範へ差し替える。結果契約§7からはtext行形式を参照するだけとし、
   Markdown固有規則を二重に書かない。
3. `diagnostic-coverage.json`の当該source hashを更新する。
4. `SINGLE-104-01`のcorpus（`SINGLE-042`と同一）、manifest、期待JSON、期待Markdown、副作用期待値を作成し、
   監査へMarkdown byte一致と、要約値がJSON結果と一致することの検査を追加する。
5. `fixtures/conformance/Step-0B検証記録.md`と実装計画の件数を更新する。
