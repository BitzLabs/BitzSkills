# 文書種別・本文テンプレート

## 1. 共通規則

Frontmatter直後の最初の非空行を`# <id> <title>`形式のH1とし、Frontmatterと一致させる。H1は1つだけとする。
不在、複数、不一致は`SPEC-STYLE-H1-001`／failedとする。

Core 1.0は全SPECへ`Revision History`を要求しない。正確な差分、変更者、時刻はGitを正とする。
重要な理由はADR、PR、commit、または任意`Notes`から安定参照できるようにする。

## 2. REQ

REQは利用者が期待する振舞いまたは制約を記述する中心的な契約である。次のH2を必須とする。

1. `Intent`
2. `Acceptance Criteria`
3. `Verification`

他のH2、順序、空の任意節はCoreの合否に使用しない。EARS-AI規範文は`Acceptance Criteria`だけに置き、
他sectionに規範行があれば`SPEC-STYLE-PLACEMENT-001`／failedとする。

```markdown
# REQ-001 有効な認証情報によるログイン

## Intent

登録済み利用者が安全にsessionを開始できるようにする。

## Acceptance Criteria

- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 有効な認証情報を受信した場合 [MUST] [THEN] access tokenを1件発行する。

## Verification

公開login APIを入口にした結合testで成功と拒否を確認する。
```

`approved` REQは1件以上の妥当なEARS-AI規範文を必要とする。0件なら`SPEC-REQ-STATEMENT-001`／failedとする。
`draft`はEARS-AI構文の一部をwarningにできるがID不正と重複はerrorとする。

`Verification`はproduction入口、重要な失敗境界、未証明事項を必要な場合だけ記述する。test実装の存在を装わず、
予定、実装済み、未証明を区別する。

## 3. TECH

TECHはREQだけでは保持できない外部から観測可能な技術契約を記録する。次を推奨templateとする。

```text
Context
Contract
Constraints       # 任意
Verification
Notes             # 任意
```

CoreはH1、Frontmatter、EARS-AI、関係、pathを検査するが、TECHのH2名と順序を合否にしない。
機械検査が必要な契約はEARS-AIで記述でき、その場合は`Contract`または`Constraints`へ置く。
他sectionの規範行は`SPEC-STYLE-PLACEMENT-001`／failedとする。規範文を持たないTECHも許可する。

REQを具体化するTECHは`refines`、理解・実行の前提は`requires`、単なる閲覧関係は`related`を使う。

## 4. ADR

ADRは重要な判断と理由を記録する。推奨templateは`Context`、`Decision`、`Consequences`、任意`Alternatives`、
任意`Notes`である。CoreはH2名と順序を合否にしない。

ADRは実装pathとtest commandを所有しない。適用側文書が`requires`で`accepted` ADRを参照する。
判断を置き換える場合は後継ADRの`supersedes`で文書全体を置換し、後継の`accepted`と旧ADRの`superseded`を
同じ変更へ含める。
ADR内のEARS-AI候補行は`SPEC-STYLE-PLACEMENT-001`／failedとし、規範契約はREQまたはTECHへ置く。

## 5. TASK

TASKは進行中作業の一時的な分割であり、要求やIssueの代替ではない。

```yaml
---
id: TASK-001
title: login endpointを実装する
status: open
relations:
  addresses:
    - REQ-001:AC-01
  requires:
    - TECH-001
changes:
  - src/auth/
  - tests/auth/
---
```

推奨templateは`Objective`、任意`Work`、`Completion Criteria`、任意`Notes`である。CoreはH2名と順序を
合否にしない。

`addresses`には実装対象の規範文IDを列挙する。規範文を持つREQ/TECHを文書IDだけで暗黙に全句対象にしない。
規範文を持たないTECHだけ文書IDを指定できる。

`requires`先TASKは`implement`または`verify`時にすべて`done`でなければならない。未完了またはcancelledなら
`CTX-TASK-DEPENDENCY-001`／blockedとする。

`changes`はfile pathまたは末尾`/`のdirectory prefixを持つ。glob、絶対path、`..`を禁止する。TASK ID/pathを
明示した`check`だけが境界を強制する。

TASK内のEARS-AI候補行は`SPEC-STYLE-PLACEMENT-001`／failedとし、対象契約は`addresses`で参照する。

## 6. rejectedとcancelled

`rejected` REQ/TECHと`cancelled` TASKは履歴として保持し、現行の所有逆索引、coverage、path存在検査、
command解決へ混ぜない。理由記録はCore必須sectionにせず、任意`Notes`、ADR、Issue、PR、commitを使用する。

Coreは文章の理由が十分かを判定しない。

## 7. templateとlinter

H2順序、空の任意section、太字疑似section、段落styleはtemplateまたは将来linterの責務とする。
Core 1.0の`check`はこれらをwarningにもせず、合否へ使用しない。

機械検査するstyle Diagnosticは次だけである。

| code | 条件 | result |
|---|---|---|
| `SPEC-STYLE-H1-001` | H1不在、複数、不一致 | failed |
| `SPEC-STYLE-SECTION-001` | REQ必須H2不在または空 | failed |
| `SPEC-STYLE-PLACEMENT-001` | 規範文が文書種別ごとの許可位置外 | failed |
