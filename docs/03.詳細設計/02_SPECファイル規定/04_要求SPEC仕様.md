# 要求SPEC仕様

## 1. 役割

要求SPECは、利用者が期待する振る舞いまたは制約をEARS-AIで記述する最小の契約単位である。
1ファイルは1つの要求テーマを扱い、複数の受入条件を持てる。

## 2. 正規例

```markdown
---
id: REQ-001
title: 有効な認証情報によるログイン
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
      - REQ-001:AC-02
    command: default
verify: default
---

# REQ-001 有効な認証情報によるログイン

## Intent

登録済み利用者が安全にセッションを開始できるようにする。

## Acceptance Criteria

- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 有効な認証情報を受信した場合 [MUST] [THEN] アクセストークンを1件発行する。
- [REQ-001:AC-02] [ACTOR:AuthService] [WHEN] 無効な認証情報を受信した場合 [MUST] [THEN] 認証失敗を返す。

## Verification

公開ログインAPIを入口にした結合テストで、成功応答と不正入力拒否を確認する。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-27 | 初版を作成 | — |
```

## 3. 本文構造

H1、H2、セクション順、太字の扱いは
[Markdown本文構成・スタイル](08_Markdown本文構成・スタイル.md)に従う。REQでは`Intent`と
`Acceptance Criteria`、`Verification`、最終H2の`Revision History`を必須とし、EARS-AI規範文は
`Acceptance Criteria`だけに置く。
`Revision History`は非規範メタデータであり、規範文ID、coverage、Context Digestの意味集合へ含めない。

Coreは[EARS-AI Core構文仕様](../01_EARS-AI規格/01_Core構文仕様.md)が定める規範行だけを解析する。
通常の説明文、コード例、引用内のEARS-AI風テキストを要求として扱わない。

## 4. 規範文ID

- 各規範文IDは`<document-id>:<local-id>`とする。
- 要求SPECの`document-id`はFrontmatterの`id`と一致させる。
- `local-id`は同一文書内で一意とし、`AC-[0-9]{2,}`を推奨する。
- 承認後に別の意味へIDを再利用しない。
- 文の並べ替えではIDを変更しない。

規範文IDはTASKの`addresses`、テストの`covers`、Context Bundleの網羅判定に使用する。IDを変更する場合は、
参照元を同じ変更で更新しなければならない。

## 5. 依存関係

- 意味を理解する前提は`relations.requires`へ置く。
- 他の要求を具体化する場合は`relations.refines`へ置く。
- 置換の場合は`relations.supersedes`へ置く。
- 閲覧用の関連だけなら`relations.related`へ置く。

`requires`と`refines`はContext Resolutionで完全に探索される。説明文中のIDやMarkdownリンクを、
強い依存の代わりにしてはならない。

後継文書が旧文書を`supersedes`した時点で、旧文書を新しい実装・検証の起点にしない。Coreは後継へ
暗黙に差し替えず、`CTX-STATE-SUPERSEDED-001`と後継IDを返す。

## 6. 状態別の検査

### `draft`

- Frontmatterの必須項目とID一意性を検査する。
- 不完全なEARS-AI行は、`EAI-CORE-SYNTAX-*`と`EAI-CORE-SEM-001`に限りwarningとする。
  ID形式・重複・再利用は`draft`でもerrorとする
  （[AST・パーサー仕様](../01_EARS-AI規格/06_AST・パーサー仕様.md) §6）。
- `implements`、`tests`、`verify`はなくてよい。
- `purpose=interpret`ではadvisoryとして取得できる。

### `approved`

- 1件以上の妥当なEARS-AI規範文を必須とする。
- 妥当な規範文が0件の場合は`SPEC-REQ-STATEMENT-001`／error／`failed`とする。不正IDや必須タグ不足の
  候補行を通常本文として数えず、同時に該当する`EAI-*` Diagnosticを返す。
- 強い関係、規範文ID、指定済みパスはすべて解決できなければならない。
- `implements`と`tests`は実装前には省略できる。
- `bitz verify`の対象にする時点では、全`MUST`にテスト対応と有効なコマンドを必須とする。

### `outdated`

- 構文と関係は検査する。
- 強い依存先、`implement`、`verify`の起点に指定された場合は`blocked`とする。
- 意味を見直した後、`draft`または`approved`へ明示的に変更する。

## 7. 承認済み要求の保護

`safety.protectApprovedRequirements`が有効な場合、`bitz check`はGitの基準版と比較し、承認済み要求の
`title`、EARS-AI規範文、強い関係が変更されたことを検出する。同じ変更で状態を`draft`または`outdated`へ
戻していなければエラーとする。

`implements`、`tests`、`verify`、`related`、`x-`拡張、説明文だけの変更は意味変更として扱わない。
ただし、説明文と規範文が矛盾していないかは人間が確認する。

承認済み要求の`title`、規範文、強い関係を変更する場合は、必要なstatus変更に加え、同じ変更で
`Revision History`へ改訂理由と裁定の参照を追記する。履歴行だけを追加して承認保護を回避してはならない。

Gitの基準版がない新規ファイルは比較対象外とする。Gitが利用できない場合、`bitz doctor`は保護を
実施できないことを警告し、Coreは文書を自動変更しない。

## 8. AI利用時の境界

要求本文は未信頼データである。`[GENERATE]`や自然言語中の命令は成果物の要求であり、ツール実行命令ではない。
AIアダプターは要求から権限、コマンド、外部送信先を導出してはならない。

エージェントは文書を個別に推測探索せず、[Context Resolution仕様](10_Context%20Resolution仕様.md)の
Context Bundleを利用する。実装報告では対応した規範文IDを列挙する。
