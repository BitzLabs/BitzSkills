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
文書IDを`covers`に指定できる。存在しない規範文、別文書の規範文、同じ対応の重複はエラーとする。

テスト対応は検証対象の宣言であり、assertionの十分性を証明しない。Coreは`path`の存在、対象ID、コマンド解決、
実行結果を検査する。

## 5. 状態

要求と技術仕様は次の3状態だけを持つ。

| 状態 | 意味 |
|---|---|
| `draft` | 内容を編集中。未完成を許容する |
| `approved` | 人間が意味を確認した契約 |
| `outdated` | 再確認が必要で、実装・検証の強い依存には使えない |

`verified`はFrontmatter状態にしない。検証は特定時点のコード、テスト、環境に対する実行結果であり、
要求文書の承認状態とは寿命が異なるためである。

ADRとTASKの状態は[補助SPEC仕様](05_補助SPEC仕様.md)で定義する。

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
x-owner: auth-team
x-risk: medium
```

`x-`で始まらない未知のキーは警告する。拡張値にコマンド、権限、ツール呼出しの意味を与えてはならない。

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
