# report非作成・引数不正fixture review

[適合fixture仕様 §6.7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#67-出力とreport)の
`SINGLE-070-01/02/03/04`と、`SINGLE-073-01/02`、`SINGLE-074-01/02/03`を扱う。
いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 既存のreportを置くことで、不変性を検査できる

matrixは「file生成0件、既存report不変」を求める。reportのない入力では前半しか示せない。既存のreportを黙って
書き換える実行でも、*新しい*fileは0件に見えるからである。そのため`SINGLE-070-*`の入力にはすべて
`.spec/reports/existing.json`を置き、snapshotにこのfileがないfixtureを監査が拒否する。不変性の半分が、
知らないうちに検査されなくなることはない。

「`--report`なしで書き込むか」は、成功する実行と失敗する実行とで別の問いなので、4件で両操作の両結果を扱う。

| fixture | 操作 | status |
|---|---|---|
| `SINGLE-070-01` | `check --full --base HEAD` | `passed`／0 |
| `SINGLE-070-02` | `check --full --base HEAD` | `failed`／1 |
| `SINGLE-070-03` | `verify REQ-001` | `passed`／0 |
| `SINGLE-070-04` | `verify REQ-001` | `failed`／1 |

verifyの2件は、`SINGLE-055`と`SINGLE-056`のreview済みの結果を書き直さずに直接使う。追加したreport fileは
SPECの材料ではないので、ContextとそのDigestは変わらない。結果を読み込むことで、2つの群がずれていくことを防ぐ。

checkの2件は、3文書と2規範文を数える。2規範文を持つ`REQ-001`、`TECH-001`、`ADR-001`である。これは、ADRを
規範文を持たない検査対象文書とする既存の慣例と一致する。`SINGLE-070-02`は、`TECH-001`が存在しない`TECH-999`を
`requires`するという単一の原因で失敗する。trace群でreview済みの`SPEC-RELATION-MISSING-001`と同じ形である。

checkの群はfixture契約どおり基準commitを作って`--base HEAD`を渡す。verifyの群は、`verify`に`--base`がなく、
未追跡の設定で停止するため、代わりにstageする。

## 引数不正は結果を一切返さない

5件の`expect`は`status`も`resultFile`も持たない。manifestの契約は、起動が共通結果を返さない場合にだけこれを許す。
どちらかを追加したmanifestは監査が拒否する。

| fixture | 起動 | 拒否の理由 |
|---|---|---|
| `SINGLE-073-01` | `context REQ-001 --report` | `--report`を受け付けるのは`check`と`verify`だけ |
| `SINGLE-073-02` | `doctor --report` | 同上 |
| `SINGLE-074-01` | `check REQ-001 --full` | `--full`と明示targetは排他 |
| `SINGLE-074-02` | `verify src/auth.py` | code pathはverifyのtargetではない |
| `SINGLE-074-03` | `check REQ-1` | 3桁未満は文書IDではない |

`SINGLE-074-03`は、IDの不在ではなく、意図して*字句*の誤りにしている。
[CLI基盤契約 §6](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#6-targetとworkspaceの不存在)は
両者を分ける。構文上妥当だが存在しないIDは操作を開始して`CTX-ROOT-MISSING-001`／failedを返し、形式不正のIDは
操作を開始しない。`REQ-1`は`[0-9]{3,}`の規則を満たさないので、後者にしかなり得ない。

## 標準エラー出力の契約を1つにし、操作を区別できるようにした

標準エラー出力の期待値はGit環境の群にあり、`bitz: check: `に固定されていた。これをcopyせず、
`check_cli_error_output`が操作を受け取るように改め、5件と以前の1件が1つの契約を共有する。終了コード4、
空の標準出力、ちょうど1行、空でない理由、端末制御文字なし、である。各fixtureの`cli-output.json`はそれぞれの
接頭辞を記録し、監査はその操作でhelperを動かして、誤った接頭辞、空の理由、2行目、4以外の終了コードを拒否する。

## 限界

- Coreは実行していない。Coreとの一致はGate Bで判定する。
- 接頭辞の後の理由文は意図して制約しない。存在することと安全であることだけを固定し、文言の変更でmatrixが
  壊れないようにする。
- `SINGLE-074-01`は排他の組を1つだけ固定する。公開構文にある他の排他（`--all-workspaces`まわり）は、このfixtureでは
  扱わない。
