# Markdown本文構成・スタイル

## 1. 目的

SPECの見出し、太字、箇条書きが書き手ごとに変わると、人間もAIも情報の所在を推測する必要がある。
Core 1.0は文書種別ごとにH1とH2を固定し、自由な詳細化はH3以下へ閉じ込める。

本文言語は`bitz.yaml`の`language`に従うが、機械的に識別するH2名は英語の固定語彙とする。

## 2. 全文書の共通規則

### 2.1 H1

Frontmatter直後の最初の非空行を、次の形式のH1とする。

```markdown
# REQ-001 有効な認証情報によるログイン
```

形式は`# <id> <title>`であり、Frontmatterの`id`と`title`に一致させる。文書内のH1は1つだけとする。

### 2.2 H2とH3

- H2は本規定が文書種別ごとに定める固定セクションだけを、定義順に使用する。
- 任意セクションは不要なら省略し、空見出しや`N/A`だけの節を作らない。
- 固有の詳細見出しが必要なら、該当H2の下でH3以下を使用する。
- セクション番号を見出しへ付けない。追加や並べ替えで番号だけのdiffが生じるためである。
- `## **Intent**`のように見出しを太字で装飾しない。

### 2.3 太字

太字は本文中で本当に強調する短い語句にだけ使用する。次の疑似セクション表現を禁止する。

```markdown
- **説明**: ...
- **完了条件**: ...
```

これらは`## Intent`や`## Completion Criteria`のような見出しへ置き換える。Coreは箇条書き先頭の
`**label**:`が標準セクションを代替している場合、`SPEC-STYLE-PSEUDO-001`を報告する。

### 2.4 本文

- 1段落は1つの論点だけを扱う。
- ソース上は1文ごとの改行を推奨する。Markdown表示上は同じ段落として扱われる。
- 箇条書きは並列な事実、表は3件以上の同じ属性を比較するときに使う。
- ID、パス、コマンド、コード上の識別子はインラインコードにする。
- EARS-AI以外の本文で大文字の`MUST`、`SHOULD`、`MAY`を規範語として使わない。
- 絵文字、HTML、折り畳み要素を意味伝達の必須手段にしない。
- 見出し、段落、リスト、コードブロックの前後に空行を1行置く。

## 3. REQ

H2は次の順序とする。

| セクション | 必須 | 内容 |
|---|:--:|---|
| `Intent` | Yes | 誰のどの問題を解くか |
| `Context` | No | 前提、用語、対象外 |
| `Acceptance Criteria` | Yes | EARS-AI規範文 |
| `Verification` | Yes | production入口、試験戦略、未証明事項 |
| `Notes` | No | 非規範の補足 |

```markdown
# REQ-001 有効な認証情報によるログイン

## Intent

登録済み利用者が安全にセッションを開始できるようにする。

## Acceptance Criteria

- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 有効な認証情報を受信した場合 [MUST] [THEN] アクセストークンを1件発行する。

## Verification

公開APIを入口にした結合テストで、成功応答と不正入力拒否を確認する。
```

REQ内のEARS-AI規範文は`Acceptance Criteria`だけに置く。他セクションにある規範文形式の行はエラーとする。
`Verification`はテスト実装の存在を装わず、予定、実装済み、未証明を文章上で明確に区別する。

## 4. TECH

H2は次の順序とする。

| セクション | 必須 | 内容 |
|---|:--:|---|
| `Context` | Yes | 技術的背景と制約 |
| `Contract` | Yes | 外部から観測できる技術契約 |
| `Constraints` | No | 性能、安全性、禁止事項 |
| `Verification` | Yes | 統合入口、異常境界、試験方法 |
| `Notes` | No | 非規範の補足 |

TECHでEARS-AIを使う場合は`Contract`または`Constraints`に置く。複雑な状態遷移、失敗原子性、
platform差分が重要な場合は、表または図をH3以下へ追加する。

## 5. ADR

H2は次の順序とする。

| セクション | 必須 | 内容 |
|---|:--:|---|
| `Context` | Yes | 判断が必要になった背景 |
| `Decision` | Yes | 採用する判断 |
| `Consequences` | Yes | 利点、費用、残る制約 |
| `Alternatives` | No | 不採用案と理由 |
| `Notes` | No | 関連情報 |

ADRの状態や後継関係はFrontmatterで表し、`Revision History`を本文へ重ねない。判断を変える場合は
既存ADRを書き換え続けず、後継ADRを作成する。

## 6. TASK

H2は次の順序とする。

| セクション | 必須 | 内容 |
|---|:--:|---|
| `Objective` | Yes | 完了時に成立する結果 |
| `Work` | No | 実装方針または作業項目 |
| `Completion Criteria` | Yes | 観測可能な完了条件 |
| `Notes` | No | 見積り、制約、引継ぎ |

```markdown
# TASK-001 ログインエンドポイントを実装する

## Objective

`REQ-001`を公開APIから利用できるようにする。

## Work

- 認証サービスをエンドポイントへ接続する。
- 受入テストを追加する。

## Completion Criteria

- `bitz verify REQ-001`が成功する。
- `bitz check .spec/tasks/TASK-001.md`が変更境界違反を報告しない。
```

作業境界のパスは本文へ列挙せず、Frontmatterの`changes`を正とする。

## 7. 検査レベル

| 条件 | severity | Diagnostic |
|---|---|---|
| H1がない、複数ある、Frontmatterと不一致 | error | `SPEC-STYLE-H1-001` |
| 必須H2がない | error | `SPEC-STYLE-SECTION-001` |
| H2が未定義または順序違反 | error | `SPEC-STYLE-SECTION-002` |
| EARS-AI規範文が許可セクション外にある | error | `SPEC-STYLE-PLACEMENT-001` |
| 太字ラベルが標準セクションを代替 | warning | `SPEC-STYLE-PSEUDO-001` |
| 空の任意セクション | warning | `SPEC-STYLE-EMPTY-001` |
| 推奨スタイルの違反 | 原則として診断しない | — |

書式検査は構造だけを扱い、文章の巧拙、意味的正しさ、十分性を自動判定しない。
