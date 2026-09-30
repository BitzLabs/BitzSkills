# `verify`の実行と事前ブロックのfixtureのレビュー記録

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify)の
`SINGLE-055`、`SINGLE-056`、`SINGLE-060`、`SINGLE-061`、`SINGLE-062`、`SINGLE-067`を扱う。
プロセス単位の入力（`SINGLE-057`、`058`、`059`、`069-01/02`）と、複数のテスト割当ての入力（`SINGLE-063`、`064`、`065`、
`066`、`068`）は別の回で扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない。

## `verify`のfixtureはすべて入力をステージする

[`verify`仕様 §5.1](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#51-実行ファイルと環境)は、Gitが使える状態で、
テスト割当てのワークスペースの設定がインデックスで未追跡なら、`VERIFY-CONFIG-UNTRACKED`で起動を遮断する。`context`のfixtureは何も
ステージしない、コミットのないリポジトリを使えたが、`verify`のfixtureではコマンドに到達せず、すべてのケースが同じ原因になってしまう。

`setup.baseCommit`ではなく`setup.operations: [{"op": "stage", "paths": ["."]}]`を使う。
[適合fixture仕様 §3](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#3-マニフェスト)は、基準版コミットを持つ
fixtureに`--base`を渡すことを求めるが、`verify`にはこのオプションがないためである。そのためリポジトリはインデックスに内容を
持つ、コミットのないままで、`revision`は`null`である。監査はインデックスを読み戻して、全ケースでステージされていることを確認する。

## ハッシュ値の再利用

`SINGLE-055`はハッシュ値の材料を変えずに実行するため、`targetResults[].contextDigest`は別の定数ではなく
`SINGLE-042`がコミットした値である。これにより`verify`の証拠がgolden値と結び付く。

| fixture | 入力の変更 | `contextDigest` |
|---|---|---|
| `SINGLE-055` | なし | コミットしたgolden値 |
| `SINGLE-056` | コマンドの`argv`を`/bin/false`へ | 固有の値（`argv`テンプレートはハッシュ値の材料） |
| `SINGLE-060` | `tests`を1件削除 | 固有の値 |
| `SINGLE-061` | `command: missing`（2件とも） | 固有の値（2026-09-26訂正。下記参照） |
| `SINGLE-062` | `draft`のREQだけ | 検証対象がないのでハッシュ値もない |
| `SINGLE-067` | `cancelled`のTASKの起点 | `null` |

`SINGLE-061`がハッシュ値を持つのは、`command`名が設定に定義されているかどうかは[`verify` §8](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#8-結果)の
「`contextDigest`はContextを構成できない場合だけnull」に言うコンテキストの構成の失敗ではなく、コンテキストを構成した後の、テスト割当ての解決だけの
失敗だからである（訂正の経緯は下記参照）。`SINGLE-067`が返さないのは、`cancelled`の起点ではコンテキストをまったく構成できない
からである。監査は、コンテキストが解決した場合に限りハッシュ値があることを強制し、両者がずれないようにする。

## 診断の置き場所

置き場所は、結果の状態ではなくレジストリの継続単位で決まる。

| fixture | 条件 | 単位 | 置き場所 |
|---|---|---|---|
| `SINGLE-060` | `CTX-COVERAGE-TEST-MUST` | `skip-target` | 検証対象の`diagnostics` |
| `SINGLE-061` | `VERIFY-BINDING-MISSING` | `skip-target` | 検証対象の`diagnostics` |
| `SINGLE-067` | `CTX-STATE-INAPPLICABLE` | `skip-target` | 検証対象の`diagnostics` |
| `SINGLE-062` | `VERIFY-TARGETS-EMPTY` | `stop-operation`、発生元`invocation` | 最上位 |

[`verify`仕様 §6](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#6-コマンドの結果)は、単一ワークスペースでは*テスト割当て*の
診断を最上位に置く。ただしこれは`skip-binding`の条件（未追跡の設定、実行ファイルの不在、使えない`cwd`、`argv`の上限、
`cwd`の外のテスト）に当てはまる規定である。`VERIFY-BINDING-MISSING`は`skip-target`なので、`SINGLE-061`は検証対象に置く。

## その他のレビュー済みの判断

- **テストコマンドは`/bin/true`と`/bin/false`とする。** 決定論的で、出力もファイルの書込みもない。
  [適合fixture仕様 §5](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#5-副作用の検査)が
  `verify`の副作用fixtureに求めるとおり、コマンド自身の書込みをCoreの書込みと混同しない。そのため両方の抜粋は`""`、
  両方の切り詰めフラグは`false`である。
- **`SINGLE-067`は`statements: []`を返す。** `cancelled`の起点は、`addresses`する参照先を展開する前に拒否される。
  検証するはずだった規範文を並べると、行われなかった作業を主張することになる。
- **`SINGLE-062`は`draft`のREQを使う。** [`verify`仕様 §7](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#7-引数なしの実行)
  は`approved`のREQとTECHだけを対象にするため、ワークスペース自体を消さずに対象0件にする最小の入力は、`draft`の文書1件である。
- **`covers`は、テスト割当てのテストが対象にする規範文を挙げる。** `argv`は、§5と§8に従い、`{tests}`を重複排除・整列した
  パスで置き換えて展開した値を持つ。

## 監査が強制する不変条件

フィールドの一致に加えて、監査は次の結果を拒否する。`bindingRefs`と`commands[]`が同じ実行の集合を表していないもの、
`bindingId`が`<workspace-id>::<command-name>`でないもの、解決できなかったコンテキストにハッシュ値があるもの。これらはmatrixの
行が挙げる性質なので、リテラルだけでなく性質として検査する。

## 限界

- Coreは実行していない。Coreとの一致はGate Bで判定する。
- `SINGLE-061`は、診断の発生元のキーを`tests[0].command`と`tests[1].command`（要素ごとに1件）とする。レジストリは
  発生元の種類を`file`と定めるが、キーは定めない。宣言順の各要素を使う。
- `/bin/false`の終了コードは1とする。Step 0Bで固定した基準環境のLinuxで、coreutilsの実行ファイルが返す値である。

## 2026-09-26の訂正（`SINGLE-061`の`contextDigest`と独立原因の分離）

2026-09-25に管理者が承認した方針（規範文の記述整備）を反映したコミットで、[`verify`仕様 §8](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#8-結果)へ
「`contextDigest`はContextを構成できない場合だけnull」が明記された。この規則と、[診断レジストリ §2](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md#2-status優先順位)の
「独立したraw原因はそれぞれprimaryを持つ」に照らすと、`SINGLE-061`の従来の期待値は2点で規範文と食い違っていた。

- **`contextDigest: null`は誤りだった。** `SINGLE-061`はコマンド名を解決できないだけで、REQ-001／TECH-001／ADR-001の
  型・状態・強い関係はすべて解決し、コンテキストは完全に構成できる（`resolution.complete`に相当する状態）。テスト割当ての
  解決の失敗は`verify`固有の後続の処理であり、コンテキストの構成そのものの失敗ではない。訂正後は、`command: missing`の入力から導ける
  固有のコンテキストのハッシュ値（`settings.commands`と`settings.verifyTimeouts`は、収録できるテスト割当てが0件なので
  ともに空の配列）を返す。
- **独立した原因は1件でなく2件だった。** `TECH-001`の`tests[]`は`test_auth.py`（`tests[0]`）と`test_session.py`（`tests[1]`）の
  2要素を持ち、どちらも同じ未定義のコマンド名`missing`を参照するが、配列の要素として独立した2つの元の原因である。訂正前は
  最初の要素だけを返しており、レジストリの「独立したraw原因はそれぞれprimary」を満たしていなかった。訂正後は`tests[0]`と
  `tests[1]`のそれぞれに診断を1件ずつ返す。

入力（`command: missing`）と診断の単位（`skip-target`、検証対象の`diagnostics`）は変えていない。
`digest_crosscheck.build`（参照計算B）も、未定義のコマンド名を参照するテスト割当てをハッシュ値の材料から静かに除外するよう
1箇所直した（従来は`commands[name]`が`KeyError`になり、コンテキストが解決するのにハッシュ値を計算できなかった）。
これは、[適合fixture仕様 §1.1](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#11-matrixとfixtureの変更)の
「期待値の訂正」に当たり、規範文（`verify` §8、診断レジストリ §2）へ合わせるものである。Core実装の観測出力を根拠にしていない。
