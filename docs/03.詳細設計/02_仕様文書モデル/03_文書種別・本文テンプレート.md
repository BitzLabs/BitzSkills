# 文書種別・本文テンプレート

## 1. 共通規則

フロントマターの直後にある最初の空行でない行を`# <id> <title>`の形のH1とし、フロントマターと一致させる。H1は1つだけとする。
H1が存在しない場合、複数ある場合、または一致しない場合は、診断`SPEC-STYLE-H1-001`（`failed`）とする。

Core 1.0は、すべての仕様文書に`Revision History`を要求しない。正確な差分、変更者、時刻はGitを正とする。
重要な理由は、ADR、PR、コミット、または任意の`Notes`から安定して参照できるようにする。

## 2. REQ

REQ（要求）は、利用者が期待する振る舞いまたは制約を記述する中心的な契約である。次のH2を必須とする。

1. `Intent`
2. `Acceptance Criteria`
3. `Verification`

ほかのH2、順序、空の任意の節は、Coreの合否に使わない。EARS-AIの規範文は`Acceptance Criteria`だけに置き、
ほかの節に規範文があれば、診断`SPEC-STYLE-PLACEMENT-001`（`failed`）とする。

```markdown
# REQ-001 有効な認証情報によるログイン

## Intent

登録済み利用者が安全にsessionを開始できるようにする。

## Acceptance Criteria

- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 有効な認証情報を受信した場合 [MUST] [THEN] access tokenを1件発行する。

## Verification

公開login APIを入口にした結合testで成功と拒否を確認する。
```

`approved`のREQは、1件以上の妥当なEARS-AI規範文を必要とする。0件であれば、診断`SPEC-REQ-STATEMENT-001`（`failed`）とする。
`draft`は、EARS-AI構文の一部を重大度`warning`にできるが、ID不正と重複は重大度`error`とする。

`Verification`は、本番の入口、重要な失敗の境界、未証明の事項を必要な場合だけ記述する。テストの実装があるように装わず、
予定、実装済み、未証明を区別する。

## 3. TECH

TECH（技術仕様）は、REQだけでは保持できない、外部から観測できる技術契約を記録する。次を推奨するテンプレートとする。

```text
Context
Contract
Constraints       # 任意
Verification
Notes             # 任意
```

Coreは、H1、フロントマター、EARS-AI、関係、パスを検査するが、TECHのH2の名前と順序は合否に使わない。
機械検査が必要な契約はEARS-AIで記述でき、その場合は`Contract`または`Constraints`へ置く。
ほかの節にある規範文は、診断`SPEC-STYLE-PLACEMENT-001`（`failed`）とする。規範文を持たないTECHも許可する。

REQを具体化するTECHは`refines`、理解・実行の前提は`requires`、単なる閲覧関係は`related`を使う。

## 4. ADR

ADR（決定記録）は、重要な判断と理由を記録する。推奨するテンプレートは`Context`、`Decision`、`Consequences`、任意の`Alternatives`、
任意の`Notes`である。CoreはH2の名前と順序を合否に使わない。

ADRは、実装のパスとテストコマンドを所有しない。適用する側の文書が`requires`で`accepted`のADRを参照する。
判断を置き換える場合は、後継のADRの`supersedes`で文書全体を置換（supersede）し、後継の`accepted`と旧ADRの`superseded`を
同じ変更へ含める。
ADR内のEARS-AI候補行は、診断`SPEC-STYLE-PLACEMENT-001`（`failed`）とし、規範契約はREQまたはTECHへ置く。

## 5. TASK

TASK（タスク）は、進行中の作業の一時的な分割であり、要求やIssueの代替ではない。

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

推奨するテンプレートは`Objective`、任意の`Work`、`Completion Criteria`、任意の`Notes`である。CoreはH2の名前と順序を
合否に使わない。

`addresses`には、実装対象の規範文IDを列挙する。規範文を持つREQまたはTECHは、文書IDだけを指定して、暗黙にそのすべての規範文を対象にしない。
規範文を持たないTECHだけ、文書IDを指定できる。

`requires`の参照先であるTASKは、`implement`または`verify`のときにすべて`done`でなければならない。未完了または`cancelled`であれば、
診断`CTX-TASK-DEPENDENCY-001`（`blocked`）とする。

`changes`は、ファイルのパスまたは末尾が`/`のディレクトリの接頭辞を持つ。glob、絶対パス、`..`を禁止する。TASKのIDまたはパスを
明示した`check`だけが境界を強制する。

TASK内のEARS-AI候補行は、診断`SPEC-STYLE-PLACEMENT-001`（`failed`）とし、対象契約は`addresses`で参照する。

## 6. `rejected`と`cancelled`

`rejected`のREQとTECH、および`cancelled`のTASKは、履歴として保持し、現行の所有逆索引、カバレッジ、パスの存在検査、
コマンドの解決へ混ぜない。理由の記録はCoreの必須の節にせず、任意の`Notes`、ADR、Issue、PR、コミットを使う。

Coreは、文章の理由が十分かどうかを判定しない。

## 7. テンプレートとリンター

H2の順序、空の任意の節、太字による疑似的な節、段落のスタイルは、テンプレートまたは将来のリンターの責務とする。
Core 1.0の`check`は、これらを警告にもせず、合否に使わない。

機械検査するスタイルの診断は、次だけである。

| コード | 条件 | 結果への効果 |
|---|---|---|
| `SPEC-STYLE-H1-001` | H1が存在しない、複数ある、または一致しない | `failed` |
| `SPEC-STYLE-SECTION-001` | REQの必須のH2が存在しない、または空である | `failed` |
| `SPEC-STYLE-PLACEMENT-001` | 規範文が文書種別ごとの許可された位置の外にある | `failed` |
