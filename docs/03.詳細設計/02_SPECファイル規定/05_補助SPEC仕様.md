# 補助SPEC仕様

## 1. 方針

Core 1.0の中心は要求SPECである。TECH、ADR、TASKは、要求だけでは判断根拠、実装境界、依存を保持できない場合に
限って追加する。既存の`docs/`、Issue、コードコメントと同じ情報を複製しない。

## 2. TECH

TECHは要求を実現するための技術的な契約を記録する。

```yaml
---
id: TECH-001
title: アクセストークン格納方式
status: approved
relations:
  refines:
    - REQ-001
  requires:
    - ADR-001
implements:
  - src/auth/token_store.py
tests:
  - path: tests/auth/test_token_store.py
    covers:
      - TECH-001:CONST-01
    command: default
verify: default
---
```

本文は`Context`、`Contract`、任意の`Constraints`、`Verification`、条件付きの`Rejection Rationale`、`Notes`、最終H2の`Revision History`で構成する。機械検査が必要な
契約はEARS-AI規範文で記述できるが、Core 1.0はTECHへEARS-AIを必須としない。状態は`draft`、
`approved`、`outdated`、`rejected`を使う。`rejected`では空でない`Rejection Rationale`を必須とし、
採用しなかった理由、根拠またはトレードオフ、再検討条件を記録する。元の`Contract`と`Verification`、
`implements`、`tests`、`verify`は履歴として保持する。ただし、パスと検証情報は所有逆索引、検証対象、coverage、
パス存在検査、検証コマンド解決へ含めない。`rejected`を強い依存先または`implement`／`verify`の起点にした場合は
`CTX-STATE-001`／error／`blocked`とする。再検討時は新しいTECH IDを作る。

REQを技術的に具体化するTECHは`refines`を使用する。単に同じテーマを扱うだけなら`related`とし、
Contextへ自動混入させない。

## 3. ADR

ADRは重要な設計判断と理由を記録する。

```yaml
---
id: ADR-001
title: アクセストークン形式にJWTを採用する
status: accepted
relations:
  related:
    - REQ-001
---
```

状態は`proposed`、`accepted`、`rejected`、`superseded`とする。作成時は`proposed`、`accepted`、
`rejected`を許可し、既存文書は`proposed -> accepted|rejected`、`accepted -> superseded`だけを遷移できる。
`rejected`と`superseded`は終端状態とする。本文は`Context`、`Decision`、
`Consequences`、任意の`Alternatives`、`Notes`、最終H2の`Revision History`で構成する。

ADRを必須制約として適用する側は、自身の`requires`からADRを参照する。ADRの`related`だけでは
Contextへ自動的に含まれない。後継ADRは`supersedes`で旧ADRを指定し、旧ADRを`superseded`へ変更する。

ADRは実装パスや検証コマンドを直接所有しない。

## 4. TASK

TASKは進行中作業の一時的な分割であり、要求やIssueの代替ではない。

```yaml
---
id: TASK-001
title: ログインエンドポイントを実装する
status: open
relations:
  addresses:
    - REQ-001:AC-01
    - REQ-001:AC-02
  requires:
    - TECH-001
changes:
  - src/auth/
  - tests/auth/
---
```

状態は`open`、`done`、`cancelled`とし、作成時は`open`、許可遷移は`open -> done|cancelled`とする。
`done`と`cancelled`は終端状態であり、追加作業または再計画には新しいTASK IDを使用する。担当者、期限、
blocked理由などはIssue管理がある場合はそちらへ置く。終端TASKのIDを別の作業へ再利用しない。本文は
`Objective`、任意の`Work`、`Completion Criteria`、条件付きの`Cancellation Rationale`、任意の`Notes`、
最終H2の`Revision History`で構成する。`cancelled`では空でない`Cancellation Rationale`を必須とし、
取り止め理由、既に得た知見、再開または再計画の条件を記録する。

TASK起点の開発フローでは、VerifyとHuman Reviewの後に起点TASKを`done`へ変更してRevision Historyを更新し、
変更後の入力へ`bitz check <TASK-ID>`を実行する。このcheckが`passed`または`passed_with_warnings`の場合だけ、
完了結果をGitへ記録する。TASK自身のファイルは`changes`境界の比較対象から除くが、状態遷移と文書検査の対象からは
除外しない。Coreはstatusを自動変更せず、後続TASKは先行TASKの完了結果をGitへ記録した後に開始する
（[ADR-034](../../02.設計書/10_決定記録/ADR-034_TASK完了終端とdone起点操作の確定.md)）。
checkの通過statusは[ADR-035](../../02.設計書/10_決定記録/ADR-035_check空対象とフロー通過statusの確定.md)を正とする。

`addresses`には実装対象のEARS-AI規範文IDを列挙する。規範文を持たないTECHだけは文書IDを指定できる。
規範文を持つREQ/TECHの文書IDだけを指定して全句を暗黙対象にすることは禁止する。
対象外の兄弟句はContext Bundleへadjacentとして表示し、
エージェントが要求全体の存在を見落とさないようにする。

`requires`はTASK実行前に必要なSPECまたは先行TASKを示す。TASK間の循環はエラーとする。
TASKを起点とする`purpose=implement`または`purpose=verify`では、`requires`が指すTASKがすべて`done`である
ことを要求する。`open`の先行TASKが残る場合は`CTX-TASK-DEPENDENCY-001`／error／`blocked`とし、未完了の
先行TASK IDを返す。`purpose=interpret`は停止せず、未完了の先行TASKをWork区分として表示する。
実行順序を持たない単なる関連作業には`related`を使い、`requires`を使わない
（[ADR-029](../../02.設計書/10_決定記録/ADR-029_TASK先行依存の状態ガード.md)）。

`done` TASKを`purpose=implement`の起点にすることは禁止し、`CTX-STATE-001`／error／`blocked`として
新しいTASKの作成を示す。`purpose=verify`は完了済み作業の再検証として許可し、`addresses`から検証対象を
導出する。`purpose=interpret`も許可し、TASKをHistory区分で返す。`verify`時の先行TASK状態ガードは
`done`の起点にも同じく適用する。

`cancelled` TASKは`purpose=interpret`でHistory区分として返し、明示`check`を許可する。
`purpose=implement`または`purpose=verify`の起点では`CTX-STATE-001`／error／`blocked`とする。
別TASKの`requires`先にある場合は完了済みとみなさず、`CTX-TASK-DEPENDENCY-001`／error／`blocked`で
依存の除去または代替TASKへの更新を示す。取り止め時は`open -> cancelled`、理由、Revision Historyを同じ変更へ
記録し、変更後の入力へ`bitz check <TASK-ID>`を実行してからGitへ記録する
（[ADR-036](../../02.設計書/10_決定記録/ADR-036_フロー取り止めと不採用履歴の保持.md)）。

`changes`は任意の変更境界である。TASK IDまたはTASKファイルpathを明示して`bitz check`すると、Gitの変更パスが
`changes`のファイルまたはディレクトリ接頭辞に含まれるかを検査する。境界の修正が必要ならTASK自身の
`changes`を人間がdiffで確認して更新する。

TASKを起点とする開発フローでは、実装後の`Post-check`で`bitz check <TASK-ID>`を実行して境界を強制する
（[ADR-028](../../02.設計書/10_決定記録/ADR-028_開発フローの実装後検査とTASK境界の接続.md)）。実装前の
汎用`bitz check`は実装で生じる変更pathを含まないため、境界保証の根拠にしない。

## 5. 関係方向

```text
REQ  --requires----> REQ / TECH / accepted ADR
REQ  --refines-----> REQ / REQ:statement
TECH --refines-----> REQ / TECH / REQ:statement / TECH:statement
TECH --requires----> REQ / TECH / accepted ADR
ADR  --requires----> REQ / TECH / accepted ADR
TASK --addresses---> REQ:statement / TECH:statement / non-normative TECH
TASK --requires----> REQ / TECH / TASK / accepted ADR
NEW  --supersedes--> OLD of same kind
ANY  --related-----> ANY
```

関係の正確な包含規則は[Context Resolution仕様](10_Context%20Resolution仕様.md)を正とする。本文中のID、
Markdownリンク、`related`を強い依存の代用にしない。

## 6. 改訂履歴

TECH、ADR、TASKはいずれも[Markdown本文構成・スタイル](08_Markdown本文構成・スタイル.md) §2.5に従い、
最終H2に`Revision History`を置く。TECHは契約・制約の変更、TASKは`changes`・対象句・完了条件の変更を
要約する。ADRは作成、非意味的訂正、後継ADRによる置換だけを記録し、Decisionの変更履歴として使わない。
履歴は非規範メタデータであり、型付き依存、Constraint Ledger、coverageの入力にしない。
