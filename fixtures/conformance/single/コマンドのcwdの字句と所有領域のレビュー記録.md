# コマンドのcwdの字句と所有領域のfixtureのレビュー記録

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の`SINGLE-167-01`〜`SINGLE-167-09`を扱う。
いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/command_cwd_fixtures.py`である。複合ワークスペースの対は[複合ワークスペースのコマンドのcwdの所有領域のレビュー記録](../multi/複合ワークスペースのコマンドのcwdの所有領域のレビュー記録.md)に記録した。

> **2026-11-15の訂正（ADR-071）。** `cwd`のシンボリックリンクを辿らず、`cwd`がディレクトリとして存在しなければ`VERIFY-CWD-UNAVAILABLE`とする（[安全な入出力・互換性 §6](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#6-正規パス)）。`VERIFY-CWD-OUTSIDE`は診断レジストリから除いた。`SINGLE-167-07`・`09`の扱いは、末尾の「2026-11-15の訂正」が上書きする。

## 追加の理由

`verify.commands.<名前>.cwd`は、設定の検査が型しか見なかった。そのため、`../..`、絶対パス、globの文字、ルートの外へ出るシンボリックリンクの`cwd`でも、
どの操作も止まらず、`verify`はテストのコマンドをワークスペースの外で起動していた。実装の確認事項C82・C86に対応する。
ユーザーの決定で、次のとおり規範に書いた。

- ワークスペース・設定仕様 §6: `cwd`の字句は、単独の`.`、または空のセグメント、`.`、`..`、NUL、globの文字`*?[]`を含まず、`/`で始まらないパスに限る。
  字句の違反は設定の検査で診断`SPEC-CONFIG-SCHEMA-001`とし、どの操作もコマンドの実行へ進まない。実パスの所有は`verify`がテスト割当ての起動前に判定し、
  単一ワークスペースで実パスがルートの外なら診断`SPEC-VERIFY-BLOCKED-001`（`blocked`）とする。
- 診断レジストリの新しい条件`VERIFY-CWD-OUTSIDE`（番号607、`skip-binding`。独立レビューの指摘で、`VERIFY-TEST-OUTSIDE-CWD`の608と入れ替えた）。
- 診断の文言（ユーザー承認済み）: 字句の違反は新しい文言「作業ディレクトリのパスの形式が不正です」、実パスの違反は既存の「コマンドの作業ディレクトリが利用できません」。
- globの文字を`*?[]`の4つにそろえる決定（確認事項C43）。そのため、閉じ括弧だけの`a]`も字句の違反である（`SINGLE-167-06`）。

## 入力と起動

全ケースは`SINGLE-042`のcorpusを基に、設定のコマンド`default`の`cwd`だけを替える。`SINGLE-126`と同じく`verify`はインデックスへステージする。
`check`は基準版のコミットを作り（`SINGLE-004-01`と同じ）、`doctor`と`context`はステージも基準版も置かない（`SINGLE-092`、`SINGLE-150`と同じ）。

| fixture | 操作 | `cwd` | 結果 |
|---|---|---|---|
| `SINGLE-167-01` | `verify REQ-001` | `../..` | `error`／3、`SPEC-CONFIG-SCHEMA-001`の1件 |
| `SINGLE-167-02` | `doctor` | `/tmp` | `error`／3、同上（`checks`の`config`が`error`） |
| `SINGLE-167-03` | `check --full --base HEAD` | `t*` | `error`／3、同上 |
| `SINGLE-167-04` | `context REQ-001 --purpose verify` | `tests//` | `error`／3、同上 |
| `SINGLE-167-05` | `verify REQ-001` | `./tests` | `error`／3、同上 |
| `SINGLE-167-06` | `verify REQ-001` | `a]` | `error`／3、同上 |
| `SINGLE-167-07` | `verify REQ-001` | `up`（`up -> ..`） | `blocked`／2、`SPEC-VERIFY-BLOCKED-001`の1件、`commands`は空 |
| `SINGLE-167-08` | `verify REQ-001` | `tests`（対照） | `passed`／0 |
| `SINGLE-167-09` | `verify REQ-001` | `inner`（`inner -> real`。対照） | `passed`／0 |

`SINGLE-167-07`の`up -> ..`は、`repo/`のコミット済みの入力では`SINGLE-167-07/`ディレクトリを指し、準備手順の後は準備手順で作る隔離したリポジトリの親を指す。
どちらでもワークスペースのルートの外であり、実パスの判定は準備手順の後の入力から導く。`SINGLE-167-09`は、テストの実体を`real/`へ移し、`TECH-001`が宣言する
テストのパスを`inner/test_auth.py`と`inner/test_session.py`にする。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **停止する結果の形**。字句の違反は設定の型の不正と同じ原因（`SPEC-CONFIG-SCHEMA-001`）で、結果の形は同じ原因の既存のfixtureがレビュー済みの形を引き継ぎ、診断だけを置き換える
   （`doctor`は`SINGLE-092`、`check`は`SINGLE-004-01`、`context`は`SINGLE-150`で目的だけ`verify`、`verify`は`SINGLE-126-01`）。
   ワークスペースの同一性を構成する前に停止するので、`workspace.id`と`source.workspaceId`は`null`（結果・診断・終了コード §2、`SINGLE-126-01`と同じ）。
2. **実パスの違反**。`VERIFY-CWD-OUTSIDE`は`skip-binding`で、`verify` §6により単一ワークスペースでは最上位の`diagnostics`へ1件だけ置き、
   影響を受ける検証対象は診断を複製せず、状態を`blocked`、`bindingRefs: []`とする。`commands`へ実行結果を作らない。`contextDigest`は、コンテキストを解決できているので持つ
   （`SINGLE-126-09`と同じ）。`source`は設定ファイルの`verify.commands.<名前>.cwd`（`verify` §5.1）で、`workspaceId`は`root`。
3. **ハッシュ値**。検証対象の`contextDigest`は、独立に書いた2系統の参照計算（`digest_reference`のリテラルにコマンドの`cwd`とテストのパスだけを加えたA、
   入力の木構造から導く`digest_crosscheck`のB）のバイト列の一致を要求する。`cwd`はコマンドの定義としてハッシュ値の材料に入る。
4. **字句と実パスの参照計算**。このモジュールの`lexical_violation`と`within`が、設定の`cwd`と準備手順の後の`realpath`から、結果の種類（字句の違反、ルートの外、通過）を導き、
   fixtureが名乗る種類と一致することを2回の準備手順のそれぞれで確かめる。

## 規範から導けなかった点・固定の程度

- `SINGLE-167-07`で、テストのパスはどれも`cwd`の配下に実在する（`up`の解決先はルートの親で、テストの実体を含む）。そのため、`VERIFY-TEST-OUTSIDE-CWD`
  （テストのパスが`cwd`の配下にない）と重ならない。包含は正規パスのセグメントの境界で判定する（ワークスペース・設定仕様 §6）ことが前提である。
- `SINGLE-167-02`の`doctor`で、設定を解釈できないときのコマンドと作業ディレクトリの検査項目を実行しない（`doctor` §3）ことは、`SINGLE-092`の`checks`の形を引き継いで固定した。
  `cwd`の字句の違反が設定の型の不正と同じ`config`の`error`になることは、診断コードが同じ`SPEC-CONFIG-SCHEMA-001`であることから導いた。

## 2026-11-15の訂正（ADR-071。ADR-051の期待値の訂正）

管理者が方針を承認した（根拠はADR-071と書き直した規範文）。

- `SINGLE-167-07`（`up -> ..`）: 末端がシンボリックリンクの`cwd`は、リンク先がルートの外でも中でも、リンクを辿らず、ディレクトリとして存在しない。診断は`VERIFY-CWD-UNAVAILABLE`
  （`SPEC-VERIFY-BLOCKED-001`、`blocked`、summary「コマンドの作業ディレクトリが利用できません」、`source`は設定ファイルの`verify.commands.default.cwd`）。診断のJSONは訂正の前と同じで、
  条件名だけが`VERIFY-CWD-OUTSIDE`から変わる（単一ワークスペースでは、字句の検査を通った`cwd`は常にルートの配下にあるので、所有の違反は生じない）。修正前のCoreも通る。
- `SINGLE-167-09`（`inner -> real`、テストは`inner/`配下）: 対照（`passed`／0）だったが、テストのパスの途中のセグメントがシンボリックリンクになるので、存在しないパスと同じに扱う。
  テストのパスの検査（`verify` §4の4.）は起動前の`cwd`の判定より前なので、検証対象が`failed`で、`SPEC-PATH-INVALID-001`が`TECH-001`の`tests[0].path`と`tests[1].path`に1件ずつ。`cwd`は判定しない。
  修正前のCoreは`passed`／0を返すので失敗する。
- 新しい`SINGLE-167-10`（`cwd: lnk/sub`、`lnk -> real`、`real/sub/keep.txt`が実在）: 途中のセグメントがシンボリックリンクの`cwd`は、リンク先に実在するディレクトリでも、存在しない。
  `VERIFY-CWD-UNAVAILABLE`の1件。テストは`tests/`のままで、字句では`cwd`の外にもあるが、`cwd`の判定が前提なので重ならない。修正前のCoreは、`cwd`の実パスで包含を判定し、
  `VERIFY-TEST-OUTSIDE-CWD`（`source`は`TECH-001`の`tests[0].path`）を返すので失敗する。
- 参照計算は`reference_outcome(repository, tests)`に書き直した（`lexical_path_reference.lookup`。`realpath`を使わない）。テストのパスの検査を`cwd`の検査より前に行う。
  新しい文言はない。
