# 文書・Frontmatter・状態仕様

## 1. 文書IDとfile名

| 種別 | ID | directory |
|---|---|---|
| REQ | `REQ-[0-9]{3,}` | `requirements/` |
| TECH | `TECH-[0-9]{3,}` | `technical/` |
| ADR | `ADR-[0-9]{3,}` | `decisions/` |
| TASK | `TASK-[0-9]{3,}` | `tasks/` |

IDはworkspace内でcase-sensitiveに一意とし、意味を持たない安定識別子とする。欠番は正常で、削除したIDを
別の意味へ再利用しない。

file名は`<ID>.md`または`<ID>-<slug>.md`とする。先頭IDとFrontmatter `id`が異なる場合は
`SPEC-FILE-NAME-001`／failedとする。参照解決はFrontmatter IDを使う。

Coreは現在集合の重複を`SPEC-ID-DUPLICATE-001`／failedとして検出するが、勝敗、新ID、書換え箇所を提案しない。

## 2. Frontmatter

すべてのSPEC Markdownはfile先頭に1つのYAML Frontmatterを持つ。前にBOM、空行、commentを置かない。
解析後の構造はDraft 2020-12の
[`fixtures/conformance/frontmatter.schema.json`](../../../fixtures/conformance/frontmatter.schema.json)に従う。
Coreは配置directoryから文書種別を決め、同Schemaの`reqFrontmatter`、`techFrontmatter`、`adrFrontmatter`、
`taskFrontmatter`の対応する定義を選んで検証する。Schema rootの`oneOf`は独立validator用であり、directoryによる
種別決定を置き換えない。

```yaml
---
id: REQ-001
title: ユーザーログイン
status: approved
relations:
  requires: [ADR-001]
implements:
  - src/auth/service.py
tests:
  - path: tests/auth/test_service.py
    covers: [REQ-001:AC-01]
    command: default
verify: default
---
```

## 3. 共通field

| key | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `id` | string | Yes | 安定文書ID |
| `title` | string | Yes | 1〜120文字の1行title |
| `status` | string | Yes | 種別ごとの状態 |
| `relations` | map | No | 型付きSPEC関係 |
| `implements` | string[] | No | 実装file path |
| `tests` | object[] | No | test pathとcoverage |
| `verify` | string | No | 文書既定command名 |
| `changes` | string[] | No（TASKだけで利用可） | 許可する変更path。省略と`[]`は許可pathなし |

文書種別はdirectoryから決め、`type`を重複して持たない。配列は重複を許さない。

- REQ/TECH: `relations`、`implements`、`tests`、`verify`
- ADR: `relations`
- TASK: `relations`、`changes`

文書種別では利用できないCore fieldは、型と値域が妥当なら`SPEC-FM-UNAVAILABLE-001`／warningとする。
型または値域が不正なら先に`SPEC-FM-SCHEMA-001`を返し、利用不能warningを重ねない。

### 3.1 null、空、文字数

Core標準fieldはすべて`null`を禁止する。`id`、`title`、`status`、`verify`、`tests[].path`、
`tests[].command`は空stringを禁止する。`title`は改行を含まない1〜120 Unicode code pointとし、少なくとも
1 code pointの非空白文字を含める。測定前のtrim、Unicode正規化、case変換を行わない。

`relations`の空mapと、`relations.*`、`implements`、`tests`、`changes`の空配列は許可する。
`tests[].covers`は1件以上を必要とする。任意fieldの省略は許可するが、空stringや`null`を省略の代用にしない。
TASKの`changes`を省略または`[]`にした場合、明示TASK `check`で許可される変更pathは0件であり、変更差分があれば
境界外として扱う。

### 3.2 未知keyと拡張値

Frontmatter直下の`x-`で始まるfieldは許可して保持し、それ以外の未知fieldはSchemaを通過させたうえで
`SPEC-FM-UNKNOWN-001`／warningとする。`relations`と`tests[]`は閉じたobjectであり、定義されていない内部keyを
`SPEC-FM-SCHEMA-001`とする。`refs`は既存の専用規則により`SPEC-RELATION-LEGACY-001`を返す。

拡張fieldと未知fieldの値は、共通YAML subsetのscalar、scalar配列、またはstring keyのmapに限る。
その内部でobject配列は使用できない。Coreは値を変更せず保持するが、合否、Context、command、権限へ使用しない。

## 4. relation field

```yaml
relations:
  requires: [REQ-010, ADR-001]
  refines: [REQ-001]
  addresses: []
  supersedes: []
  related: [TECH-009]
```

Core語彙は`requires`、`refines`、`addresses`、`supersedes`、`related`だけとする。意味と型は
[関係・トレースモデル](04_関係・トレースモデル.md)が定義する。旧`refs`は曖昧なためerrorとし、自動変換しない。

## 5. test対応

`tests`要素は次を持つ。

| key | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `path` | string | Yes | workspace相対test file |
| `covers` | string[] | Yes | 対応する規範文ID |
| `command` | string | No | `bitz.yaml` command名 |

REQまたはEARS-AIを含むTECHでは`covers`へ同じ文書の規範文IDを指定する。規範文を持たないTECHだけ文書IDを
指定できる。存在しない句と同じ対応の重複はerrorとする。モノレポで文書が別workspaceの文書または規範文を
直接`refines`する場合だけ、そのtargetを修飾IDで`covers`に指定できる。横断coverageの詳細は
[モノレポSPEC連合仕様](05_モノレポSPEC連合仕様.md)に従う。

command名は`tests[].command`、文書の`verify`の順で解決する。どちらもない場合、または解決したcommand名が
`bitz.yaml`に存在しない場合、`verify`は`SPEC-VERIFY-BLOCKED-001`／blockedとする。

test対応は対象宣言であり、assertionの十分性を証明しない。

## 6. 状態

### 6.1 REQ／TECH

| 状態 | 意味 |
|---|---|
| `draft` | 編集中。構文の一部warningを許容 |
| `approved` | 人間が意味を確認した適用可能な契約 |
| `outdated` | 再確認が必要で実装・検証に適用不能 |
| `rejected` | 不採用の終端履歴 |

許可遷移は`draft -> approved|rejected`、`approved -> draft|outdated`、`outdated -> draft|approved`である。
`rejected`は終端とする。同一状態維持を許可する。

### 6.2 ADR

状態は`proposed`、`accepted`、`rejected`、`superseded`とする。許可遷移は
`proposed -> accepted|rejected`、`accepted -> superseded`で、`rejected`と`superseded`は終端とする。

### 6.3 TASK

状態は`open`、`done`、`cancelled`とする。許可遷移は`open -> done|cancelled`で、`done`と`cancelled`は終端とする。

禁止遷移は`SPEC-STATE-TRANSITION-001`／error／failedとする。Git基準版がない場合、現在語彙だけを検査し、
過去状態を推測しない。基準版に存在しない新規文書は現在状態が種別語彙として妥当なら許可する。

## 7. 適用可能性

- `approved` REQ/TECHと`accepted` ADRだけを規範的な強い依存先にできる。
- `draft`は`interpret`でadvisory、`implement`/`verify`起点ではblocked。
- `outdated`と`rejected`は強い依存先または`implement`/`verify`起点でblocked。
- `approved`の有効な後継から`supersedes`されたREQ／TECHは適用不能になる。旧文書のstatusは自動変更せず、
  Coreは起点を後継へ暗黙差替えしない。
- `done` TASKは`verify`再実行と`interpret`を許し、`implement`起点ではblocked。
- `cancelled` TASKは`interpret`だけを許す。

## 8. 承認済みREQ保護

保護有効時、`check`はGit基準版の`approved` REQと現在版を比較する。`title`、EARS-AI規範文、強い関係を
変更しながらstatusを`draft`または`outdated`へ戻していない場合、`SPEC-SAFETY-APPROVED-001`／failedとする。

`implements`、`tests`、`verify`、`related`、`x-`拡張、説明文だけの変更は意味変更に含めない。
Git基準版に存在しない新規REQは比較対象外とする。

## 9. 管理済み文書の削除

基準版と現在版は`documentId`で対応付け、pathだけの変更はrenameとして同じ文書とする。基準版のIDが現在版に
存在しない場合、種別や状態を問わず`SPEC-STATE-TRANSITION-001`／failedとする。

Core検査を迂回した過去の削除後再利用をGit全履歴から検出することは保証しない。

「削除したIDを別の意味へ再利用しない」は規範として維持するが、Core 1.0はこれを機械検査しない。
Coreが保証するのは現在集合の重複検出（`SPEC-ID-DUPLICATE-001`）と、基準版から現在版への
管理済みSPEC削除の検出（`SPEC-STATE-TRANSITION-001`）までであり、2時点比較では同一文書の改訂と
別の意味での再出現を区別できない。基準版より前の履歴における再利用の禁止はGitレビューの責務とする。
[ADR-032](../../02.設計書/10_決定記録/ADR-032_ID再利用検出のCore保証範囲.md)が定義していた
`EAI-CORE-ID-003`は、[ADR-037](../../02.設計書/10_決定記録/ADR-037_Git基準版間のSPEC同一性と削除規則.md)に
よる置換に伴いCore 1.0の公開Diagnosticから外し、codeを予約済みとする。

## 10. 拡張

project固有fieldは`x-<name>`とする。Coreは保持するが合否、Context、command、権限へ使用しない。

```yaml
x-owners: [auth-team]
x-risk: medium
```

`x-`で始まらない未知fieldは`SPEC-FM-UNKNOWN-001`／warningとする。

## 11. YAML制約

- 構文層は[workspace・設定仕様 §8](01_workspace・設定仕様.md#8-yaml制約)の共通YAML 1.2 subset
- Frontmatter 32 KiB以下、文書全体1 MiB以下
- 標準fieldの構造はFrontmatter Schemaを正とし、`tests`だけobject配列を許可
- mapping keyの同値性はYAML解釈後のstringのcode point完全一致で判定する
- Frontmatter内の全配列は、fieldごとに次の重複規則を適用する

scalar配列の重複は、YAML解釈後の値と型の完全一致で判定し、Unicode正規化、case変換、path補正を行わない。
`tests`要素は`(path, commandの有無と値, covers集合)`をkey tupleとする。`covers`集合は値のcode point辞書順で
比較するため、記述順だけが異なる要素も重複である。mapping keyの記述順は同値性へ影響しない。
同じ`path`でも`command`または`covers`が異なる要素は許可する。重複配列はfieldの値域不正として
`SPEC-FM-SCHEMA-001`を返す。

Frontmatter YAMLの構文不正、禁止構文、重複key、fieldの型・値域不正は
`SPEC-FM-SCHEMA-001`／error／`failed`とする。必須field欠如だけは
`SPEC-FM-REQUIRED-001`／error／`failed`とする。同じraw原因へ両codeを返さない。
