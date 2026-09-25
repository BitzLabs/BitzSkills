# verify実行・事前ブロックfixture review

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify)の
`SINGLE-055`、`SINGLE-056`、`SINGLE-060`、`SINGLE-061`、`SINGLE-062`、`SINGLE-067`を扱う。
process単位の入力（`SINGLE-057`、`058`、`059`、`069-01/02`）と、複数bindingの入力（`SINGLE-063`、`064`、`065`、
`066`、`068`）は別の回で扱う。いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## verify fixtureはすべて入力をstageする

[verify仕様 §5.1](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#51-実行fileと環境)は、Gitが使える状態で
bindingのworkspace設定がindexで未追跡なら、`VERIFY-CONFIG-UNTRACKED`で起動を遮断する。Context fixtureは何も
stageしないunbornのrepositoryを使えたが、verify fixtureではcommandに到達せず、すべてのcaseが同じ原因になってしまう。

`setup.baseCommit`ではなく`setup.operations: [{"op": "stage", "paths": ["."]}]`を使う。
[適合fixture仕様 §3](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#3-manifest)は、基準commitを持つ
fixtureに`--base`を渡すことを求めるが、`verify`にはこのoptionがないためである。そのためrepositoryはindexに内容を
持つunbornのままで、`revision`は`null`である。監査はindexを読み戻して、全caseでstageされていることを確認する。

## Digestの再利用

`SINGLE-055`はDigestの入力を変えずに実行するため、`targetResults[].contextDigest`は別の定数ではなく
`SINGLE-042`がcommitした値である。これによりverifyの証拠がgoldenと結び付く。

| fixture | 入力の変更 | `contextDigest` |
|---|---|---|
| `SINGLE-055` | なし | commitしたgolden |
| `SINGLE-056` | commandの`argv`を`/bin/false`へ | 固有の値（`argv` templateはDigest材料） |
| `SINGLE-060` | `tests`を1件削除 | 固有の値 |
| `SINGLE-061` | `command: missing`（2件とも） | 固有の値（2026-09-26訂正。下記参照） |
| `SINGLE-062` | draftのREQだけ | targetがないのでDigestもない |
| `SINGLE-067` | cancelledのTASK起点 | `null` |

`SINGLE-061`がDigestを持つのは、`command`名が設定に定義されているかどうかは[verify §8](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#8-結果)の
「`contextDigest`はContextを構成できない場合だけnull」に言うContext構成の失敗ではなく、Context構成後のbinding解決だけの
失敗だからである（訂正の経緯は下記参照）。`SINGLE-067`が返さないのは、cancelledの起点ではContextをまったく構成できない
からである。監査は、Contextが解決した場合に限りDigestがあることを強制し、両者がずれないようにする。

## Diagnosticの置き場所

置き場所は、statusではなくregistryの継続単位で決まる。

| fixture | 条件 | 単位 | 置き場所 |
|---|---|---|---|
| `SINGLE-060` | `CTX-COVERAGE-TEST-MUST` | `skip-target` | targetの`diagnostics` |
| `SINGLE-061` | `VERIFY-BINDING-MISSING` | `skip-target` | targetの`diagnostics` |
| `SINGLE-067` | `CTX-STATE-INAPPLICABLE` | `skip-target` | targetの`diagnostics` |
| `SINGLE-062` | `VERIFY-TARGETS-EMPTY` | `stop-operation`、source `invocation` | 最上位 |

[verify仕様 §6](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#6-command結果)は、単一workspaceでは*binding*の
Diagnosticを最上位に置く。ただしこれは`skip-binding`の条件（未追跡の設定、実行fileの不在、使えないcwd、argvの上限、
cwd外のtest）に当てはまる規定である。`VERIFY-BINDING-MISSING`は`skip-target`なので、`SINGLE-061`はtargetに置く。

## その他のreview済みの判断

- **test commandは`/bin/true`と`/bin/false`とする。** 決定論的で、出力もfile書込みもない。
  [適合fixture仕様 §5](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#5-副作用の検査)が
  verifyの副作用fixtureに求めるとおり、command自身の書込みをCoreの書込みと混同しない。そのため両方の抜粋は`""`、
  両方の切り詰めflagは`false`である。
- **`SINGLE-067`は`statements: []`を返す。** cancelledの起点は、`addresses`する参照先を展開する前に拒否される。
  検証するはずだった規範文を並べると、行われなかった作業を主張することになる。
- **`SINGLE-062`はdraftのREQを使う。** [verify仕様 §7](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#7-引数なし実行)
  はapprovedのREQとTECHだけを対象にするため、workspace自体を消さずに対象0件にする最小の入力は、draftの文書1件である。
- **`covers`は、bindingのtestが対象にする規範文を挙げる。** `argv`は、§5と§8に従い、`{tests}`を重複排除・整列した
  pathで置き換えて展開した値を持つ。

## 監査が強制する不変条件

fieldの一致に加えて、監査は次の結果を拒否する。`bindingRefs`と`commands[]`が同じ実行の集合を表していないもの、
`bindingId`が`<workspace-id>::<command-name>`でないもの、解決できなかったContextにDigestがあるもの。これらはmatrixの
行が挙げる性質なので、literalだけでなく性質として検査する。

## 限界

- Coreは実行していない。Coreとの一致はGate Bで判定する。
- `SINGLE-061`は、Diagnosticのsource keyを`tests[0].command`と`tests[1].command`（要素ごとに1件）とする。registryは
  sourceの種類を`file`と定めるが、keyは定めない。宣言順の各要素を使う。
- `/bin/false`の終了コードは1とする。Step 0Bで固定した基準環境のLinuxで、coreutilsの実行fileが返す値である。

## 2026-09-26の訂正（`SINGLE-061`の`contextDigest`と独立原因の分離）

2026-09-25に管理者が承認した方針（規範文の記述整備）を反映したcommitで、[verify仕様 §8](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#8-結果)へ
「`contextDigest`はContextを構成できない場合だけnull」が明記された。この規則と、[Diagnostic registry §2](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md#2-status優先順位)の
「独立したraw原因はそれぞれprimaryを持つ」に照らすと、`SINGLE-061`の従来の期待値は2点で規範文と食い違っていた。

- **`contextDigest: null`は誤りだった。** `SINGLE-061`はcommand名を解決できないだけで、REQ-001／TECH-001／ADR-001の
  型・状態・強い関係はすべて解決し、Contextは完全に構成できる（`resolution.complete`に相当する状態）。binding解決の
  失敗はverify固有の後続処理であり、Context構成そのものの失敗ではない。訂正後は、`command: missing`の入力から導ける
  固有のContext Digest（`settings.commands`と`settings.verifyTimeouts`は、収録できるbindingが0件なのでともに空配列）を返す。
- **独立原因は1件でなく2件だった。** `TECH-001`の`tests[]`は`test_auth.py`（`tests[0]`）と`test_session.py`（`tests[1]`）の
  2要素を持ち、どちらも同じ未定義command名`missing`を参照するが、array要素として独立した2つのraw原因である。訂正前は
  最初の要素だけを返しており、registryの「独立したraw原因はそれぞれprimary」を満たしていなかった。訂正後は`tests[0]`と
  `tests[1]`それぞれにDiagnosticを1件ずつ返す。

入力（`command: missing`）とDiagnostic単位（`skip-target`、targetの`diagnostics`）は変えていない。
`digest_crosscheck.build`（参照計算B）も、未定義command名を参照するbindingをDigest材料から静かに除外するよう
1箇所直した（従来は`commands[name]`が`KeyError`になり、Contextが解決するのにDigestを計算できなかった）。
これは、[適合fixture仕様 §1.1](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#11-matrixとfixtureの変更)の
「期待値の訂正」に当たり、規範文（verify §8、registry §2）へ合わせるものである。Core実装の観測出力を根拠にしていない。
