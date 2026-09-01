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
| `changes` | string[] | TASKのみNo | 許可する変更path |

文書種別はdirectoryから決め、`type`を重複して持たない。配列は重複を許さない。

- REQ/TECH: `relations`、`implements`、`tests`、`verify`
- ADR: `relations`
- TASK: `relations`、`changes`

利用できないCore fieldはwarningとする。

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
| `covers` | string[] | Yes | 同じ文書の規範文ID |
| `command` | string | No | `bitz.yaml` command名 |

REQまたはEARS-AIを含むTECHでは`covers`へ同じ文書の規範文IDを指定する。規範文を持たないTECHだけ文書IDを
指定できる。別文書の句、存在しない句、同じ対応の重複はerrorとする。

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

## 10. 拡張

project固有fieldは`x-<name>`とする。Coreは保持するが合否、Context、command、権限へ使用しない。

```yaml
x-owners: [auth-team]
x-risk: medium
```

`x-`で始まらない未知fieldはwarningとする。

## 11. YAML制約

- UTF-8 YAML 1.2 subset
- Frontmatter 32 KiB以下、文書全体1 MiB以下
- custom tag、anchor、alias、merge key、重複keyを禁止
- scalar、scalar配列、通常mapだけを許可
- 日時の暗黙型変換を行わない
