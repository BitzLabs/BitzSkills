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

本文は`Context`、`Contract`、任意の`Constraints`、`Verification`、`Notes`で構成する。機械検査が必要な
契約はEARS-AI規範文で記述できるが、Core 1.0はTECHへEARS-AIを必須としない。状態は`draft`、
`approved`、`outdated`を使う。

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

状態は`proposed`、`accepted`、`rejected`、`superseded`とする。本文は`Context`、`Decision`、
`Consequences`、任意の`Alternatives`、`Notes`で構成する。

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

状態は`open`と`done`だけとする。担当者、期限、blocked理由などはIssue管理がある場合はそちらへ置く。
完了したTASKは削除してもよいが、そのIDを別の作業へ再利用しない。本文は`Objective`、任意の`Work`、
`Completion Criteria`、任意の`Notes`で構成する。

`addresses`には実装対象のEARS-AI規範文IDを列挙する。規範文を持つREQ/TECHの文書IDだけを指定して
全句を暗黙対象にすることは禁止する。対象外の兄弟句はContext Bundleへadjacentとして表示し、
エージェントが要求全体の存在を見落とさないようにする。

`requires`はTASK実行前に必要なSPECまたは先行TASKを示す。TASK間の循環はエラーとする。

`changes`は任意の変更境界である。TASKファイルを明示して`bitz check`すると、Gitの変更パスが
`changes`のファイルまたはディレクトリ接頭辞に含まれるかを検査する。境界の修正が必要ならTASK自身の
`changes`を人間がdiffで確認して更新する。

## 5. 関係方向

```text
REQ  --requires----> REQ / TECH / accepted ADR
TECH --refines-----> REQ / TECH
TECH --requires----> REQ / TECH / accepted ADR
TASK --addresses---> REQ:statement / TECH:statement
TASK --requires----> REQ / TECH / TASK / accepted ADR
NEW  --supersedes--> OLD of same kind
ANY  --related-----> ANY
```

関係の正確な包含規則は[Context Resolution仕様](10_Context%20Resolution仕様.md)を正とする。本文中のID、
Markdownリンク、`related`を強い依存の代用にしない。
