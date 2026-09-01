# Frontmatter共通仕様

## 1. 形式

すべてのSPEC Markdownは、ファイル先頭のYAML Frontmatterを1つ持つ。

```yaml
---
id: REQ-001
title: ユーザーログイン
status: approved
relations:
  requires:
    - ADR-001
implements:
  - src/auth/service.py
tests:
  - path: tests/auth/test_service.py
    covers:
      - REQ-001:AC-01
    command: default
verify: default
---
```

開始・終了区切りは行頭の`---`とし、Frontmatterより前にはBOM、空行、コメントを置かない。

## 2. 共通項目

| キー | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `id` | string | Yes | 文書の安定ID |
| `title` | string | Yes | 人間向けの短い名称 |
| `status` | string | Yes | 種別ごとの状態 |
| `relations` | map | No | 型付きSPEC関係 |
| `implements` | string[] | No | 実装ファイルの相対パス |
| `tests` | object[] | No | テストファイルと対象規範文の対応 |
| `verify` | string | No | 文書既定の検証コマンド名 |

`title`は1行で1文字以上120文字以下とする。配列は重複を許さず、正規出力ではIDまたはパスの辞書順に並べる。

`id`はworkspace内で一意な安定識別子とし、意味を持たない。ディレクトリ移動、ファイル名変更、本文改訂で
変更しない。ID形式と一意性の範囲は[配置・命名・探索規則](01_配置・命名・探索規則.md) §4を正とする。

`id`を変更してよいのは、並行branchのID衝突を解決する改番だけとする。改番はGit基準版に到達していない
文書に限り、基準版に存在する文書のIDを変更してはならない。基準版に存在するIDを持つ文書が現在版から
消えた場合は、改番ではなく削除として扱う
（[ADR-037](../../02.設計書/10_決定記録/ADR-037_Git基準版間のSPEC同一性と削除規則.md) Decision 3）。
改番の判定、勝敗、正規手順は[UC-13](../../02.設計書/09_ユースケース設計.md)を正とする。

改番はstatusを変更せず、`supersedes`による置換でもない。改番した文書は`Revision History`へ1行追記し、
`Summary`へ旧IDと改番の理由を記録する。Coreはこの追記を強制しない。

## 3. 型付き関係

```yaml
relations:
  requires:
    - REQ-010
    - ADR-001
  refines:
    - REQ-001
  supersedes: []
  related:
    - TECH-009
```

Core語彙は`requires`、`refines`、`addresses`、`supersedes`、`related`だけとする。関係の意味、source/target型、
循環、Contextへの包含規則は[Context Resolution仕様](10_Context%20Resolution仕様.md)を正とする。

汎用`refs`は使用しない。単なる閲覧関係は`related`、解釈に必須なら`requires`として意図を明示する。
`refs`を検出した場合は、曖昧な関係を暗黙変換せず`SPEC-RELATION-LEGACY-001`を報告する。

## 4. テスト対応

`tests`の各要素は次を持つ。

| キー | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `path` | string | Yes | ワークスペース相対のテストファイル |
| `covers` | string[] | Yes | このファイルが対象とする規範文ID |
| `command` | string | No | `bitz.yaml`のコマンド名。省略時は文書の`verify` |

```yaml
tests:
  - path: tests/auth/test_service.py
    covers:
      - REQ-001:AC-01
      - REQ-001:AC-02
    command: default
```

REQまたはEARS-AIを含むTECHでは、`covers`に同じ文書が所有する規範文IDを列挙する。規範文を持たないTECHだけ、
文書IDを`covers`に指定できる。存在しない規範文、許可されない別文書の規範文、同じ対応の重複はエラーとする。

モノレポでは例外として、REQまたはTECHが別workspaceの規範文を直接`refines`する場合、または別workspaceの
文書を直接`refines`する場合、その対象規範文または対象文書が所有する規範文の修飾IDを自身の
`tests[].covers`へ指定できる。テストpathとcommandは宣言文書のworkspaceが所有し、推移的な依存、
`requires`、`related`だけを根拠に別workspaceの句をcoverすることは禁止する。

テスト対応は検証対象の宣言であり、assertionの十分性を証明しない。Coreは`path`の存在、対象ID、コマンド解決、
実行結果を検査する。

## 5. 状態

要求と技術仕様は次の4状態だけを持つ。

| 状態 | 意味 |
|---|---|
| `draft` | 内容を編集中。未完成を許容する |
| `approved` | 人間が意味を確認した契約 |
| `outdated` | 再確認が必要で、実装・検証の強い依存には使えない |
| `rejected` | 採用しないと決定した終端履歴。現行の実装・検証には使えない |

`verified`はFrontmatter状態にしない。検証は特定時点のコード、テスト、環境に対する実行結果であり、
要求文書の承認状態とは寿命が異なるためである。

有効な後継REQ/TECHから`supersedes`されている文書は、状態値を増やさず論理的な置換済み文書として扱う。
置換済み文書は`approved`であっても実装・検証に適用できない（[ADR-012](../../02.設計書/10_決定記録/ADR-012_置換済みREQ・TECHの適用禁止.md)）。

ADRとTASKの状態は[補助SPEC仕様](05_補助SPEC仕様.md)で定義する。

状態遷移は次を正とする。同一状態の維持は全種別で許可する。

| 種別 | 作成時 | 許可遷移 | 終端状態 |
|---|---|---|---|
| REQ／TECH | `draft`、`approved`、`rejected` | `draft -> approved`、`draft -> rejected`、`approved -> draft`、`approved -> outdated`、`outdated -> draft`、`outdated -> approved` | `rejected` |
| ADR | `proposed`、`accepted`、`rejected` | `proposed -> accepted`、`proposed -> rejected`、`accepted -> superseded` | `rejected`、`superseded` |
| TASK | `open` | `open -> done`、`open -> cancelled` | `done`、`cancelled` |

禁止遷移は`SPEC-STATE-TRANSITION-001`／error／`failed`とする。遷移検査には
[Git基準版](../../02.設計書/10_決定記録/ADR-025_Git基準版とcheck明示対象の確定.md)を使用する。
基準版を利用できない場合も現在値の語彙は検査するが、過去状態を推測して遷移合格を宣言しない。

遷移表の「作成時」列は、文書を新規に作成するときに書いてよい状態を定める規約である。Git基準版に
存在しない文書の遷移検査は、現在値が当該種別の語彙として妥当かだけを検査し、`[new]`からの遷移として
扱う。branch内で`open -> done`まで進めたTASKが基準版に存在しない場合も、初出として許可する。
比較対象がない検査を成立させないという扱いは、承認済みREQ保護（[要求SPEC仕様](04_要求SPEC仕様.md) §7）と
同じ原則である。

基準版の文書と現在版の文書は`(workspaceId, documentId)`で対応付ける。pathの一致は要求せず、
pathだけが異なる場合はrenameとして同一文書に扱う。対応付けと削除の効果は
[ADR-037](../../02.設計書/10_決定記録/ADR-037_Git基準版間のSPEC同一性と削除規則.md)を正とする。

基準版で同一の`(workspaceId, documentId)`が複数pathへ解決する場合、そのキーの対応付けを一意に定められない。
このとき当該キーの遷移検査、削除判定、承認済みREQ保護を実施不能とし、`SPEC-BASE-AMBIGUOUS-001`／error／
`blocked`とする。暗黙に通過させない。現在集合の重複検査、現在値の語彙検査、他キーの遷移・削除・保護判定は
通常どおり実施する。基準版の重複は、並行branchのID衝突を解決する過程で一時的に生じる
（[UC-13](../../02.設計書/09_ユースケース設計.md)）。
状態変更と人間確認の境界は[ADR-024](../../02.設計書/10_決定記録/ADR-024_SPEC文書の状態遷移契約.md)および
[ADR-036](../../02.設計書/10_決定記録/ADR-036_フロー取り止めと不採用履歴の保持.md)に従う。

## 6. 種別固有項目

文書種別は配置ディレクトリから決定し、`type`キーを重複して持たない。

- `requirements/`: `relations`、`implements`、`tests`、`verify`を使用できる。
- `technical/`: `relations`、`implements`、`tests`、`verify`を使用できる。
- `decisions/`: `relations`だけを使用できる。
- `tasks/`: `relations`と種別固有の`changes`を使用できる。

利用できないCore項目が指定された場合は警告する。

TASKの`changes`は文字列配列で、意図した変更範囲を表す。ファイルパスと末尾`/`のディレクトリ接頭辞を
使用できるが、globとルート外参照は禁止する。`changes`はTASKを明示して`bitz check`した場合だけ強制する。

## 7. 拡張

プロジェクト固有項目は`x-<name>`形式にする。Coreは値を変更せず保持し、合否判定へ使用しない。

```yaml
x-owners: [auth-team]
x-risk: medium
```

`x-`で始まらない未知のキーは警告する。拡張値にコマンド、権限、ツール呼出しの意味を与えてはならない。

`ACTOR`が表す実行主体と、作成者・承認者・説明責任者は別軸である。後者を記録する場合は
`x-owners`のようなプロジェクト拡張を使い、Coreの共通項目へ追加しない
（[Core構文仕様](../01_EARS-AI規格/01_Core構文仕様.md) §2.2）。

## 8. 正規出力順

SerializerがFrontmatterを整形する場合は、`id`、`title`、`status`、`relations`、`implements`、`tests`、
`verify`、`changes`、`x-`拡張、その他の未知項目の順に出力する。`relations`は`requires`、`refines`、
`addresses`、`supersedes`、`related`の順とする。Parserは入力順を合否判定へ使用しない。

## 9. YAML制約

- UTF-8のYAML 1.2 subsetを使用する。
- scalar、scalar配列、通常のmapだけを許可する。
- カスタムタグ、アンカー、エイリアス、merge key、重複キーを禁止する。
- Frontmatterは32 KiB以下、文書全体は1 MiB以下とする。
- 日時の暗黙型変換を行わず、scalarはSchemaが要求する型で解釈する。
