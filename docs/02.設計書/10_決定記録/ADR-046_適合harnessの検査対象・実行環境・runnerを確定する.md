---
id: ADR-046
title: 適合harnessの検査対象・実行環境・runnerを確定する
status: accepted
relations:
  requires:
    - ADR-043
    - ADR-045
---

# ADR-046 適合harnessの検査対象・実行環境・runnerを確定する

## Context

[適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)はマニフェストの形と準備手順を定めるが、
harnessの外部仕様は次の点で閉じていない。このため、`SINGLE-127-15`〜`19`、`MONO-023`、`MONO-024`の期待値と
起動の方法を一意に書けない。

- `runner: bitz`が、「検査対象の`bitz` entry point」をどこから得るか。Pythonのバージョンを切り替える手段もない。
- マニフェストの`env`は固定の文字列だけなので、一時ディレクトリに置いた偽のGitを`PATH`で指せない。Git 2.30以上の場合は、
  偽のGitが実際のGitへ処理を委ねる必要があるが、その実際のGitのパスはホストに依存する。Coreがバージョンをどう取得するかも規範にない。
- CPython 3.11での動作を保証する`SINGLE-127-19`は、`doctor`を1回起動するだけでは、「3.11で利用できない構文・APIへの
  依存がない」ことを示せない。
- `runner: consumer`と`runner: migration`は、「Core配布物に含める固定compatibility harness」とあるだけで、引数列、
  出力、終了コードが未定義である。`SINGLE-127-17`／`18`は、パッケージのメタデータとロックファイルを検査するが、ロックファイルは
  配布物ではなくソースの木構造にあり、Coreが自分自身を申告する形では、独立した証拠にならない。

## Decision

1. **検査対象の受取り**: harnessは、検査対象のCoreを、ソースディレクトリまたはwheelとして、CLIの引数で受け取り、マニフェストへは
   書かない。要求されるCPythonのマイナーバージョンごとに、`uv`で、リポジトリと隔離した`HOME`の外に環境を作り、候補とロックした依存だけを
   導入する。`runner: bitz`は、その環境のコンソールスクリプト`bitz`を、シェルなしで起動する。環境の構築は起動の前に行い、
   Coreの副作用の比較には含めない。
2. **Pythonのバージョン**: `runner: bitz`の`invocation`は、任意の`python`（`<major>.<minor>`）を持てる。指定したときは、そのマイナーバージョンの
   CPythonで環境を作り、見つからなければfixtureをエラーとし、スキップしない。省略したときは、基準環境のCPythonを使う。
   `SINGLE-127-19`は、`python: "3.11"`で`doctor`を起動する。加えてGate Cでは、全matrixを、下限のCPython 3.11と基準環境の
   2つの環境で通すことを要求する。`python`を指定したfixtureは、指定したバージョンだけで判定する。
3. **Gitのバージョンの差替え**: `runner: bitz`の`invocation`は、任意の`gitVersion`（`<major>.<minor>.<patch>`）を持てる。
   harnessは、起動専用の空のディレクトリへ`git`のシムを置き、そのディレクトリを`PATH`の先頭へ加える。シムは
   `git --version`にだけ`git version <gitVersion>`の1行を返して終了コード0とし、それ以外の引数列は、シムを作成するときに解決した
   実際のGitへ、そのまま渡す。準備手順はシムを使わない。`gitVersion`と`env.PATH`は同時に指定しない。
   Coreは、`git --version`の標準出力の1行目を`git version <major>.<minor>[.<残り>]`として解析し、メジャーバージョンとマイナーバージョンを数値で
   比較する。終了コードが0以外の終了や、解析できない出力は、実行不能と同じくGit不在とする。
4. **JSON互換のランナー**: `runner: consumer`と`runner: migration`は、Core配布物のモジュール`bitz.compat`を、
   `python -m bitz.compat <runner> <argv...>`として、シェルなしで起動する。標準出力は`{"outcome": "<値>"}`の
   JSON 1件とLFで、終了コードは`accepted`と`passed`が0、`rejected`が1とする。それ以外の終了は、fixtureのエラーとする。
   `consumer`の`result-shape <path>`は、指定したJSONを、共通の結果契約の排他的な外形で判定する。`migration`のケース名と引数は、
   `MONO-024`を作成するときに、同じ形で固定する。
5. **パッケージのランナー**: パッケージのメタデータとロックファイルの検査は、Core配布物ではなく、fixtureのharnessの参照実装が行う
   `runner: package`とする。Coreの実行体を起動せず、候補のソースの木構造、ビルドの成果物、この`Decision`の1番目の項目の隔離環境に導入された
   メタデータを検査し、この`Decision`の4番目の項目と同じ出力と終了コードを返す。ケースは、`metadata`（配布物名、`import`パッケージ名、
   コンソールスクリプト名が`bitz`で、`requires-python`が3.11以上を許す）と`dependencies`（実行時の依存が、標準ライブラリと、
   ロックファイルで厳密なバージョンへ固定したYAMLのライブラリ1つだけ）の2つとする。

## Consequences

- マニフェストへホスト固有のパスを書かずに、`SINGLE-127-15`〜`19`を固定できる。Gitの下限の判定は、バージョンの取得方法まで
  決まるため、実装の間で縮退の判定が分かれない。
- 3.11の保証は、fixture 1件の起動の確認と、Gate Cの全matrixの実行の2段になる。Gate Cの実行時間はおよそ2倍になる。
- `bitz.compat`はCore配布物の一部になり、二重読取りの利用側の判定を、アダプターやCIが再利用できる。
  公開する構文は、`consumer`と`migration`の2つのランナーとケース名に限る。
- パッケージの検査はharness側にあるため、Coreが自分の配布形態を自己申告するだけでは合格しない。
- harnessは、`uv`と、`python`の指定に応じたCPythonを、ホストに要求する。不足はfixtureのエラーであり、合格扱いにしない。

## Alternatives

1. **マニフェストの`env`にプレースホルダーを許す**: `${FIXTURE_ROOT}`や`${HOST_GIT}`を展開させれば、リポジトリ内のシムを指せるが、
   マニフェストへホスト依存の展開規則が入り、同じ規則をすべての`env`の値へ適用する必要が生じる。採用しない。
2. **相対の`PATH`の要素を、`invocation`の作業ディレクトリを基準に解決する規則をCoreへ課す**: fixtureがGitのバージョンの判定とは別のCoreの挙動に依存し、
   単一の原因の原則に反する。採用しない。
3. **`SINGLE-127-19`を削除して、Gate Cだけにする**: 下限のバージョンで実際に起動できることを、適合matrixの1行として
   早期に確認できなくなる。採用しない。
4. **パッケージの検査も`bitz.compat`へ含める**: ロックファイルは配布物に含まれず、Coreの自己申告になる。採用しない。
5. **すべてのランナーをharness側の参照実装にする**: `MONO-023`がCoreではなくharnessを検査することになり、Coreの受入の
   証拠にならない。採用しない。
6. **検査対象を、実行ファイルのパスだけで受け取る**: 単純だが、Pythonのバージョンの切替えと、導入メタデータの検査に、
   別の手段が必要になる。採用しない。

## Notes

- 本ADRは、[提案27](../../04.提案資料/27_適合harness外部仕様の検討.md)の裁定である。
- ADR-043の適合matrixとADR-045の実行環境と配布物を変更せず、未確定だった適合harnessの外部仕様を追加する。
  `Decision`の3番目の項目のバージョンの取得方法と、`Decision`の4番目の項目の`bitz.compat`は、ADR-045を具体化するもので、下限バージョンと配布物名は変えない。
- 反映先: [適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、
  [Core実行環境・CLI基盤契約](../../03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md)、
  [実装計画](../../04.提案資料/12_Core-1.0実装計画.md)、`fixtures/conformance/manifest.schema.json`。
- fixture ID`MONO-023`、`MONO-024`は、後続の[ADR-047](ADR-047_複合workspaceの識別子をmultiWorkspaceへ改名する.md)で`MULTI-023`、`MULTI-024`へ改名した。
- fixtureが`repo/`で表せない入力（上限の境界の生成入力、メンバーのパスのサブモジュールまたは別のワークツリー）は、後続の[ADR-048](ADR-048_適合fixtureの生成入力とGit構造operationを確定する.md)で`setup.generate`とGit構造の準備の処理として加えた。
- `Decision`の2番目の項目の下限バージョン（`python: "3.11"`とGate Cの下限のCPython 3.11）と、`Decision`の5番目の項目の`metadata`のケースの`requires-python`は、
  後続の[ADR-053](ADR-053_CPythonの下限を3.12へ引き上げる.md)で3.12へ部分改訂した。`invocation.python`の意味と、
  ほかの`Decision`の項目は変更していない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-17 | 検査対象の受取り、Python・Git versionの指定、JSON互換runner、package runnerを確定 | 提案27 |
| 2026-09-17 | 複合workspaceの識別子の改名を後続決定へ接続 | ADR-047 |
| 2026-09-18 | fixtureの生成入力とGit構造operationを後続決定へ接続 | ADR-048 |
| 2026-09-24 | Decision 2の下限版とDecision 5のrequires-pythonを3.12へ部分改訂 | ADR-053 |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
