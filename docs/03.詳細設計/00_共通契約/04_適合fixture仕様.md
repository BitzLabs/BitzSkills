# 適合fixture仕様

## 1. 本書の範囲

本書はCore 1.0の適合試験の正本である。fixtureの配置、マニフェスト、共通の正規化器（normalizer）、比較の規則、
最小matrixを所有する。各fixtureが期待する動作の根拠は、当該契約を所有する仕様が定義し、
本書はそれを再定義しない。

Core 1.0の実装の受入れは、バージョン管理した本matrixの全fixtureが通過することを条件とする。
matrixは最小集合であり、実装は追加のfixtureを持ってもよいが、本matrixの行を削除・緩和できない。

`MULTI-*`の由来は[提案23 §8](../../04.提案資料/23_複合workspace残存P2裁定案.md#8-f-適合fixtureと期待matrix)、
`SINGLE-*`の由来は[提案24](../../04.提案資料/24_Core-1.0実装着手方針.md)である。提案資料は検討の履歴であり、
適合条件の正本は本書とする。

### 1.1 matrixとfixtureの変更

Gate Aの認定後にmatrixの行、またはfixtureの入力、期待値、副作用の期待値を変更する場合は、変更を次の4種類に分け、
種類ごとの条件を満たす。判断の理由は
[ADR-051](../../02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)に記録する。

| 種類 | 対象 | 条件 |
|---|---|---|
| 追加 | matrixの行、またはfixtureの新設 | 期待する動作の根拠となる規範文を示す |
| 期待値の訂正 | 期待結果、期待するテキスト、副作用の期待値、構文解析器の期待値が規範文と食い違うもの | 規範文に合わせる。規範文自体を直す必要があれば先に規範文を変更し、決定に関わる場合はADRを起こす。人間の管理者の承認を要する |
| 削除・緩和 | 到達できない条件、規範文どうしの矛盾 | 規範文の側で裁定し、根拠を規範文へ注記する。人間の管理者の承認を要する |
| 非意味的な変更 | 名前、形式、検証基盤の整備で、入力と期待する動作が変わらないもの | 監査が通過する |

Core実装の観測出力は、期待値の訂正、削除、緩和の根拠にしない。Coreがfixtureを通過しないことは、
それだけではfixtureの欠陥を示さない。次のいずれかにあたる変更は緩和とする。

- 期待する状態、終了コード、診断、レポート、副作用の制約を弱める
- 入力を変えて、fixtureが検査する条件が成立しなくなるようにする
- 正規化器または比較の範囲を広げる

変更の際は次を行う。

1. 追加、期待値の訂正、削除・緩和では、根拠の規範文と変更内容を、該当するfixture群のレビュー記録へ日付付きの節で記録する。
2. fixtureの変更とCore実装の変更を同じコミットに含めない。
3. `uv run fixtures/validate_conformance.py`を通し、`uv run fixtures/certify_gate_a.py`でGate Aを再認定して、
   結果を適合fixture検証記録へ残す。
4. 診断の網羅表（`fixtures/conformance/diagnostic-coverage.json`）の根拠文書が変わる場合は、網羅表を再度レビューする。
5. Gate Bが`Passed`になったStepの完了条件に含まれるfixtureを変更した場合は、そのStepのGate Bを判定し直す。

## 2. 配置

```text
fixtures/conformance/single/<fixture-id>/repo/...
fixtures/conformance/single/<fixture-id>/changes/...
fixtures/conformance/single/<fixture-id>/manifest.json
fixtures/conformance/single/<fixture-id>/expected/<operation>.json
fixtures/conformance/single/<fixture-id>/expected/<operation>.txt
fixtures/conformance/single/<fixture-id>/expected/parser-ir.json
fixtures/conformance/multi/<fixture-id>/repo/...
fixtures/conformance/multi/<fixture-id>/changes/...
fixtures/conformance/multi/<fixture-id>/dataset.json
fixtures/conformance/multi/<fixture-id>/manifest.json
fixtures/conformance/multi/<fixture-id>/expected/<operation>.json
fixtures/conformance/manifest.schema.json
```

`repo/`は基準版コミットを作る前の入力の木構造とする。`changes/`は`setup.operations[]`の`source`からだけ参照できる
固定入力であり、実行リポジトリへは自動でコピーしない。通常ファイルのバイト列と実行ビット、シンボリックリンクの
リンク文字列をバージョン管理する。Gitの履歴と基準版コミット後の状態は、マニフェストだけから構築する。
`expected/<operation>.txt`は、テキスト出力を比較するfixtureだけが持つ。
`dataset.json`は`setup.generate`を持つ生成fixtureだけが持ち、そのfixtureは`repo/`を持たない（§3.4）。
`manifest.schema.json`は全マニフェストが従う機械可読なスキーマであり、harnessは実行前にマニフェストを検証する。
契約の正本である公開結果とフロントマターのスキーマは[`docs/03.詳細設計/schemas/`](../schemas/)に置き、
fixtureは参照するだけで写しを持たない（[ADR-050](../../02.設計書/10_決定記録/ADR-050_契約スキーマの正本を詳細設計へ置く.md)）。
`result.schema.json`は、Core 1.0の全公開JSON結果が従うJSON Schema（Draft 2020-12）である。harnessは期待結果を実行前に、
実際の結果とレポートを正規化器の適用前に検証し、いずれかが不適合ならfixtureの比較自体をエラーにする。
`frontmatter.schema.json`は、YAML解析後のフロントマター構造が従うJSON Schema（Draft 2020-12）である。harnessは配置ディレクトリから
文書種別ごとの定義を選び、Coreの実行とは独立に正例を受理し、スキーマの反例を拒否することを確認する。

内部の構文解析器受入は§4.1の追加比較とし、公開する起動の回数を増やさない。
1つのfixtureは1回の起動、1種類の独立した原因、1つの期待する状態、1つの期待する終了コードだけを持つ。
並び順や集約を検査するfixtureは、同じ原因を複数箇所で発生させてもよいが、別の原因を混ぜてはならない。
同じ論点の入力の種類、操作の種類、成功または非成功の種類は、fixture ID、入力ディレクトリ、マニフェストを分ける。
共通の入力を物理的に共有するシンボリックリンク、ハードリンク、親ディレクトリの参照は使用しない。

fixture IDは`SINGLE-NNN`または`MULTI-NNN`をケースファミリーとし、分割が必要なファミリーは
`SINGLE-NNN-NN`または`MULTI-NNN-NN`を使う。計画文書の`SINGLE-001`〜`006`のような範囲表記は、
その範囲に属する接尾辞付きfixtureをすべて含む。接尾辞なしのファミリーIDと接尾辞付きIDを同時に使ってはならない。

## 3. マニフェスト

```json
{
  "fixtureId": "SINGLE-031",
  "description": "approved REQの意味変更でstatusを戻していない",
  "setup": {
    "git": true,
    "baseCommit": {"message": "base", "paths": ["."]},
    "operations": [
      {
        "op": "update",
        "path": ".spec/REQ/REQ-031_example.md",
        "source": "changes/REQ-031_example.md"
      }
    ]
  },
  "invocation": {
    "runner": "bitz",
    "cwd": ".",
    "argv": ["check", "--base", "HEAD", "--format", "json"],
    "env": {}
  },
  "expect": {
    "status": "failed",
    "exitCode": 1,
    "stdout": "json",
    "resultFile": "expected/check.json",
    "reportFileCount": 0
  }
}
```

| キー | 必須 | 意味 |
|---|:--:|---|
| `fixtureId` | ○ | 本matrixのID |
| `description` | ○ | 検査する論点の1行要約 |
| `setup.git` | ○ | Gitのリポジトリを作るかどうか。`false`はGit不在のfixture |
| `setup.generate` | — | 生成する入力。`repo/`と排他。§3.4 |
| `setup.baseCommit` | — | 基準版コミットの作り方。省略時はコミットを作らない |
| `setup.operations` | ○ | 基準版コミットの後に順番に適用する準備の処理。0件でも配列を置く |
| `invocation.runner` | ○ | `bitz`、`consumer`、`migration`、`package`のいずれか |
| `invocation.cwd` | ○ | `repo/`から相対の実行ディレクトリ |
| `invocation.argv` | ○ | 選択した`runner`へ渡す引数列。`bitz`では`bitz`に続く引数。シェルを介さない |
| `invocation.env` | ○ | 追加の環境変数。0件でもキーを置く |
| `invocation.python` | — | `bitz`だけ。起動するCPythonの`<major>.<minor>`。§3.5 |
| `invocation.gitVersion` | — | `bitz`だけ。Gitのシムが返す`<major>.<minor>.<patch>`。§3.5 |
| `expect.status` | — | 結果を返す起動では必須。引数不正で結果を返さない場合だけ省略する |
| `expect.outcome` | — | `consumer`、`migration`、`package`だけで必須。`accepted`、`rejected`、`passed`のいずれか |
| `expect.exitCode` | ○ | 期待する終了コード |
| `expect.stdout` | ○ | `json`、`text`、`markdown`、`none`のいずれか |
| `expect.resultFile` | — | 期待するJSON。`stdout: none`では持たない |
| `expect.resultDigest` | — | 生成fixtureの期待結果について、正規JSONのSHA-256。`resultFile`と排他 |
| `expect.textFile` | — | 期待するテキストまたはMarkdown。`stdout: text|markdown`で必須 |
| `expect.reportFileCount` | ○ | 実行後に`.spec/reports/`へ増える件数 |
| `parserChecks` | — | §4.1の内部の構文解析器受入。`path`と`resultFile`を持つ配列 |

`runner: bitz`はシェルを介さず、§3.5の隔離環境にある検査対象のコンソールスクリプト`bitz`を実行する。
`runner: consumer`と`runner: migration`は、Core配布物のモジュール`bitz.compat`を同じ隔離環境で
`python -m bitz.compat <runner> <argv...>`としてシェルなしで実行する。`runner: package`はCoreの実行体を起動せず、
fixture harnessの参照実装が、検査対象のソースの木構造、ビルド成果物、隔離環境への導入メタデータを検査する。
この3つの`runner`は、Coreの結果の`status`ではなく`outcome`を返す。標準出力は`{"outcome": "<値>"}`のJSON 1件とLFであり、
`expect.resultFile`は同じオブジェクトを持つ。終了コードは`accepted`と`passed`が0、`rejected`が1であり、
それ以外の終了はfixtureのエラーとする。

| `runner` | ケース（`argv[0]`） | 内容 |
|---|---|---|
| `consumer` | `result-shape <path>` | 指定したJSONを[結果・診断・終了コードの仕様 §2](01_結果・診断・終了コード.md#2-結果の形)の排他的な外形で判定する |
| `migration` | `MULTI-024`で固定 | 複合ワークスペース化と完全なロールバックの適用、部分的なロールバックの拒否 |
| `package` | `metadata` | 配布物名、`import`パッケージ名、コンソールスクリプト名が`bitz`であり、`requires-python`が3.12以上を許容する |
| `package` | `dependencies` | ランタイム依存が標準ライブラリと、ロックファイルで厳密なバージョンへ固定したYAMLライブラリ1つだけである |

`migration`は、`setup`で適用済みの変更集合が、原子的な複合ワークスペース化（`root`から`multiWorkspace`宣言とメンバー
登録への一括切替え）、または完全なロールバック（複合ワークスペース宣言と修飾参照を残さず単一ワークスペース形式へ戻す）に
なっているかを読取り専用で検証する。修飾参照が1件でも残る部分的なロールバックは`rejected`とする。Core（`bitz.compat`）は
この検証のためにファイルを書き換えない。

`consumer result-shape`は、指定したJSONが次のどちらか一方の外形だけを満たす場合に`accepted`とする。

- 単一ワークスペース外形: 最上位に`workspace`を持ち、`multiWorkspace`と`workspaces`を持たない。
- 複合ワークスペース外形: 最上位に`multiWorkspace`と`workspaces`の両方を持ち、`workspace`を持たない。

両外形の固有キー（`workspace`と、`multiWorkspace`または`workspaces`）を同時に持つ場合、またはどちらの固有キーも
持たない場合は、排他的外形の違反として`rejected`とする。

マニフェストは1つの正確な終了コードと、状態または`outcome`を記録する。範囲、選択肢、条件分岐、`元statusと同じ`、
`成功・非成功`のような入力依存の表現を書かない。
`setup.baseCommit`を持つfixtureは、`--base`を`argv`へ明示する。Coreは既定ブランチとマージベースを
推測しないため、fixtureも推測に依存しない。

### 3.1 準備手順の適用順序

harnessは各fixtureを新しい一時ディレクトリへコピーし、次の順で準備手順を適用する。

1. `repo/`の通常ファイルとディレクトリを一時ディレクトリへコピーする。シンボリックリンクはシンボリックリンクとして再作成する。
2. `setup.git: true`なら`git init`し、同一性、時刻、既定ブランチ名をharnessの固定値にする。
3. `setup.baseCommit`があれば、その`paths[]`だけをステージして1コミットを作る。
4. `setup.operations[]`を配列順に適用する。
5. Gitのインデックス、作業ツリー、ファイル種別、ファイルのバイト列がマニフェストどおりであることを確認してから起動を開始する。

`setup`用のGitの値は、既定ブランチ`fixture`、`user.name=Bitz Fixture`、`user.email=fixture@bitz.invalid`、
作成者とコミッターの日時`2000-01-01T00:00:00Z`、`commit.gpgSign=false`、`core.autocrlf=false`、
`core.fileMode=true`に固定する。ホスト側のグローバルまたはシステムのGit設定を読まず、フックを実行しない。

`setup.git: false`では、`baseCommit`、`stage`の準備の処理、起動の`--base`を禁止する。
`setup.git: true`かつ`baseCommit`なし、`operations: []`が、コミットのないリポジトリを表す。
`baseCommit`あり、`operations: []`が、クリーンなコミット済みの状態を表す。状態名を別のフィールドで重複指定しない。

### 3.2 準備の処理

各準備の処理は次の閉じた集合とする。全パスは、fixtureの一時リポジトリのルートからの`/`区切りの相対パスであり、
空のパス、絶対パス、`.`、`..`セグメント、NULを禁止する。`source`はfixtureディレクトリからの相対パスで、
`changes/`配下の通常ファイルまたはシンボリックリンクだけを指す。準備の処理はシェルを介さない。シンボリックリンクの
`source`と対象は参照解決せず、リンク文字列そのものをコピー・比較する。

| `op` | 必須フィールド | 事前条件 | 結果 |
|---|---|---|---|
| `create` | `path`, `source` | `path`が存在しない | `source`のファイル種別、バイト列またはリンク文字列、実行ビットを再現する |
| `update` | `path`, `source` | `path`が通常ファイルまたはシンボリックリンクとして存在する | `source`のファイル種別、バイト列またはリンク文字列、実行ビットで置換する |
| `delete` | `path` | `path`がファイル、シンボリックリンク、またはディレクトリとして存在する | シンボリックリンクを参照解決せず対象の木構造だけを削除する |
| `rename` | `from`, `to` | `from`が存在し、`to`が存在しない | ファイル、シンボリックリンク、ディレクトリの木構造を同じファイルシステム内で移動する |
| `stage` | `paths` | `setup.git: true` | 列挙したパスだけに`git add -A -- <paths...>`相当を適用する |
| `submodule` | `path`, `source` | `path`が存在せず`setup.git: true` | `source`ディレクトリの内容を持つ別リポジトリを`path`へ作り、親のインデックスへgitlinkと`.gitmodules`を記録する |
| `worktree` | `path`, `source` | `path`が存在せず`setup.git: true` | `source`ディレクトリの内容だけを持つコミットを作り、`path`を同じリポジトリの別ワークツリーとして追加する |

未知のフィールドは禁止する。`paths`は1件以上で重複を禁止し、`.`はリポジトリ全体を明示するときだけ許可する。
`submodule`と`worktree`の`source`だけは`changes/`配下のディレクトリを指し、その中の通常ファイルとシンボリックリンクを再現する。
両方の準備の処理は、harnessが固定した同一性、時刻、ブランチ名を使い、2回の`setup`で同じGit構造とコミットIDを与える
（[ADR-048](../../02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造の準備の処理を確定する.md)）。
`create`、`update`、`rename`で親ディレクトリがなければharnessが作成する。`delete`後に空になった親ディレクトリは残す。
`rename`と`delete`のGit上の判定はGit自身に委ねるが、期待するインデックス／作業ツリーの状態は、後続の`stage`の有無で一意に決まる。

### 3.3 実成果物との対応

matrixの各行は同名のfixtureディレクトリを1つ持ち、そのディレクトリは`manifest.json`、`repo/`、必要に応じた
`changes/`、およびマニフェストから参照される全`expected/`ファイルを持たなければならない。matrixだけに存在するID、
マニフェストだけに存在するID、参照先がないファイル、マニフェストから参照されない期待ファイルは、適合試験の開始前のエラーとする。

期待結果のフィールドと診断が後続の規範修正で変わる場合も、選択的な期待値を置いてはならない。
当該fixtureを未確定のまま実行対象へ入れず、契約確定と同じ変更で唯一の期待ファイルを追加する。

### 3.4 生成入力

リソース上限の境界のように、入力の木構造をバージョン管理できない大きさになるfixtureは、`repo/`の代わりに
`setup.generate`を持つ。`setup.generate`は、`dataset`（fixtureディレクトリ相対のデータセットのマニフェスト）と
`treeDigest`（生成した木構造の期待するハッシュ値）を必須とし、未知のフィールドを禁止する。harnessは§3.1の準備手順より前に、
データセットのマニフェストから入力の木構造を決定論的に生成し、ハッシュ値が一致しなければfixtureのエラーとする。

木構造のハッシュ値は、生成した木構造の全ファイルをパス昇順に並べ、`<repository root相対path>`、NUL、
`<内容のbyte長を8 byte big endianで表した値>`、`<内容>`を連結したバイト列のSHA-256とし、`sha256:`を前置した
小文字16進64桁とする。生成器は同じバイト列をファイルシステムへ書かずに流せるものとし、ハッシュ値の照合へ実体化を要求しない。

生成fixtureは、期待結果と副作用の期待値も同じデータセットのマニフェストから導き、`expect.resultDigest`（期待結果の
正規JSONのSHA-256）と副作用の`stateDigest`で固定する。`expect.resultFile`と`resultDigest`は排他とし、
生成物を期待ファイルとしてバージョン管理しない。レビューの対象は生成器とデータセットのマニフェストとする。

データセットのマニフェストは、上限を超える1つの次元と、その他の次元を通常規模へ保つベースラインだけを持つ。
生成器はfixture harness側の参照実装であり、Coreの実装ではない。Step 0Bの既定の検証は、同じデータセットのマニフェストを
一定比率で縮小した規模の設定で生成器の決定論と次元の計数を照合し、実寸の生成と木構造のハッシュ値の照合は
独立した`scale`の検証（`uv run fixtures/validate_scale.py`）で行う。Gate Aの認定は`scale`の検証の記録を必要とする。

### 3.5 検査対象と実行環境

harnessは、検査対象のCoreをソースディレクトリまたはwheelとしてCLI引数で受け取り、マニフェストへ書かない。
要求されるCPythonのマイナーバージョンごとに、`uv`でリポジトリ、`HOME`、`XDG_CACHE_HOME`、`TMPDIR`のいずれとも別の
ディレクトリへ環境を作り、候補とロック済みの依存だけを導入する。環境構築は準備手順より前に行い、§5の副作用比較へ含めない。

`invocation.python`を指定したfixtureは、そのマイナーバージョンのCPythonで作った環境を使う。該当するCPythonを用意できなければ
fixtureのエラーとし、スキップしない。省略したfixtureは基準環境のCPythonを使う。

`invocation.gitVersion`を指定したfixtureでは、harnessは起動専用の空ディレクトリへ実行可能な`git`のシムを置き、
そのディレクトリを起動環境の`PATH`の先頭へ加える。シムは、`argv`が`--version`だけのとき`git version <gitVersion>`と
LFを標準出力へ書いて終了0とし、それ以外の`argv`はシムの作成時に解決した実際のGitへ変更せず渡す。§3.1の準備手順は
シムを使わない。`gitVersion`と`env.PATH`は同時に指定しない。Coreのバージョン判定は
[Core実行環境・CLI基盤契約 §4](06_Core実行環境・CLI基盤契約.md#4-git)に従う。

## 4. 共通正規化器

比較の前に、実際の結果と期待するJSONの双方へ同じ正規化器を適用する。除外するのは次だけとする。

- `durationMs`（最上位、`workspaces[]`、`commands[]`のすべて）
- レポートのファイル名に含まれる生成時刻と連番
- GitのコミットID。`revision.base`と`revision.commit`は「40桁の小文字16進」であることだけを検査する
- `core.version`のパッチ部
- 実行環境に依存するプロセス出力の抜粋

除外するフィールドをfixtureごとに追加してはならない。上記以外のフィールド、値、配列順、`null`と空配列の区別、
キーの有無はすべて構造比較する。コンテキストのハッシュ値は除外せず、期待値との完全一致を要求する。

テキストの比較はUTF-8のバイト列の完全一致とする。ただし、実際の出力と期待するテキストの双方について、ASCII正規表現
`\([0-9]+ms\)`に一致する所要時間のトークンだけを`(<duration>ms)`へ置換する。行全体やトークン前後の空白、
状態、スコープ、件数は除外しない。一致するトークンが1行に複数あればすべて置換する。

コンテキストのハッシュ値のfixtureは、ハッシュ値の材料の正規JSONを、UTF-8・BOMなし・末尾改行なしのバイト列として
`expected/context.canonical.json`へ置き、そのバイト列から計算した小文字16進64桁の値を`sha256:`付きで
期待結果へ記録する。harnessは、正規JSONのバイト一致とハッシュ値の文字列の一致を別々に検査する。
単一ワークスペースのgoldenは`SINGLE-042`、複合ワークスペースのgoldenは`MULTI-002-01`が所有する。両fixtureは、マニフェストから個別に
再構築した隔離済みコピーを2つ実行し、正規JSONとハッシュ値が各回でバイト一致することも検査する。ロケール、入力ファイルの作成順、キャッシュの有無を
一度に混ぜず、個別の再現性試験として同じgolden値へ一致させる。

### 4.1 内部の構文解析器受入

`context`の公開結果には、意味中間表現の`source`や`raw`を追加しない。matrixが要求する
完全な意味中間表現の比較は、同じfixture入力を使う内部の構文解析器受入として行う。公開する起動では従来どおり
結果JSONとコンテキストのハッシュ値を比較し、内部比較の成功で公開結果の比較を代用しない。

`parserChecks`を持つマニフェストは、次のオブジェクトを1件以上列挙する。未知のフィールドを禁止する。

- `path`: `setup`後のリポジトリのルート相対の文書パス。通常ファイルに限定する。
- `resultFile`: `expected/`配下の、完全な意味中間表現の期待するJSON。各項目は異なる入力パスと期待ファイルを持つ。

期待するJSONは、文書が所有する全規範文の意味中間表現のオブジェクト配列とし、`source`の行、列、ID順で保持する。
フィールドは[EARS-AI仕様 §6](../01_EARS-AI/01_EARS-AI言語・意味中間表現仕様.md#6-意味中間表現)に従う。
`source.path`は入力パス、位置はフロントマターを含む元ファイルのUnicodeコードポイント単位の1始まりとする。
`source.column`は規範文IDの開始角括弧を指す。`raw`はリストマーカーを含む候補行全体で、改行を含めない。
`source`、`raw`、`unknownExtensions`を含む全フィールド、値、配列順、`null`と省略を比較し、正規化器で除外しない。

Step 0Bでは、固定した入力・完全な意味中間表現の期待値の整合と検証器の改変検出だけを確認する。
Step 2のGate Bでは、実装側のテストアダプターが実際の走査器／構文解析器を同じ`setup`済みの入力へ適用し、
得られた全部の意味中間表現を完全に比較する。公開するCLIオプション、公開する`runner`、製品の出力フィールドは追加しない。
アダプターが存在しない場合は未受入とし、fixture側の参照計算を実装の代わりに呼んで合格にしてはならない。
内部の構文解析器の呼出しにも§5の読取り専用の副作用条件を適用する。該当する`context`機能のGate Bでは、別途その公開結果を比較する。

## 5. 副作用の検査

全fixtureは、実行前後でGitの状態とファイルシステムのマニフェストを比較する。

- `--report`なしでは、成功・非成功にかかわらず、ファイル生成、既存レポートの更新、ワークスペース内外へのCoreの書込みを0件とする。
- `--report`指定時は、`check`と`verify`だけが規定の場所へ1件を排他的に作成する。
- 引数不正、`context`、`doctor`は、`--report`の指定の有無にかかわらずレポートを作らない。
- Coreは`.spec/`、コード、テストを変更しない。

生成fixtureの副作用の期待値は、実行前後の観測値を正規JSONのSHA-256（`stateDigest`）で固定する。
読取り専用の要求は同じで、実行前後の観測値が同じハッシュ値になることを要求する。

ファイルシステムのマニフェストは、入れ子を含むすべての`.git`ディレクトリと、別ワークツリーの`.git`ファイルを除外する。
Gitのメタデータそのものは比較対象ではなく、作業ツリーのファイルと親リポジトリの状態・インデックスで観測する。

harnessは、fixtureごとにリポジトリとは別の空ディレクトリを`HOME`、`XDG_CACHE_HOME`、`TMPDIR`として割り当て、その3つの木構造も
実行前後で比較する。Coreが暗黙に永続キャッシュ、索引、ロックファイル、作業用ディレクトリを作れば、fixture失敗とする。
明示したレポートの原子的な作成に使う一時ファイルは、規定のレポートディレクトリ内だけに許し、操作終了時には残存0件とする。
`verify`のCore副作用fixtureは、ファイルを書かない固定のテストコマンドを使い、テストプロセス自身の副作用と分離する。

## 6. 最小matrix: 単一ワークスペース

### 6.1 導入と設定

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-001` | 最小の`bitz.yaml`だけのワークスペース | doctor | passed／0 | `core`、`checks[]`、レポート0件 |
| `SINGLE-002` | `.spec/bitz.yaml`不在 | doctor | blocked／2 | `SPEC-DOCTOR-WORKSPACE-001`、最小設定の`suggestedAction` |
| `SINGLE-003` | `schemaVersion`が未知のメジャーバージョン | check | blocked／2 | `SPEC-CONFIG-SCHEMA-001`、索引を作らない |
| `SINGLE-004-01` | 設定フィールドの型不正 | check | error／3 | `SPEC-CONFIG-SCHEMA-001`、`source.key` |
| `SINGLE-004-02` | 設定の必須キーの欠如 | check | error／3 | `SPEC-CONFIG-SCHEMA-001`、`source.key` |
| `SINGLE-005-01` | 未知の標準キー | check | passed_with_warnings／0 | `SPEC-CONFIG-UNKNOWN-001`だけ。値を変更しない |
| `SINGLE-005-02` | 予約キー`profiles` | check | passed_with_warnings／0 | `SPEC-CONFIG-UNKNOWN-001`だけ。値を変更しない |
| `SINGLE-006-01` | 解決できないコマンドの実行ファイル | doctor | blocked／2 | `SPEC-DOCTOR-COMMAND-001` |
| `SINGLE-006-02` | 解決できないコマンドの`cwd` | doctor | blocked／2 | `SPEC-DOCTOR-COMMAND-001` |

### 6.2 EARS-AIと文書

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-007` | `approved`のREQにおけるタグの順序不正 | check | failed／1 | `EAI-CORE-SYNTAX-001`、行・列 |
| `SINGLE-008` | 同じ違反を`draft`で持つ | check | passed_with_warnings／0 | 同じコードが`warning`へ降格 |
| `SINGLE-009-01` | 桁不足ID | check | failed／1 | `EAI-CORE-ID-001`。本文として見逃さない |
| `SINGLE-009-02` | 未知接頭辞ID | check | failed／1 | `EAI-CORE-ID-001`。本文として見逃さない |
| `SINGLE-009-03` | 3階層ID | check | failed／1 | `EAI-CORE-ID-001`。本文として見逃さない |
| `SINGLE-010-01` | GFMのチェックボックス | check | passed／0 | 候補抽出の走査器が誤検出しない |
| `SINGLE-010-02` | コードスパン内の角括弧 | check | passed／0 | 候補抽出の走査器が誤検出しない |
| `SINGLE-011` | 規範文ID重複 | check | failed／1 | `draft`でも`EAI-CORE-ID-002` |
| `SINGLE-012-01` | 未閉鎖のタグ | check | failed／1 | `EAI-CORE-SYNTAX-004` |
| `SINGLE-012-02` | 未閉鎖のコードスパン | check | failed／1 | `EAI-CORE-SYNTAX-005` |
| `SINGLE-012-03` | 句点欠落 | check | failed／1 | `EAI-CORE-SYNTAX-006` |
| `SINGLE-013` | 未知の名前空間の拡張タグ | check | passed_with_warnings／0 | `EAI-EXT-UNKNOWN-001`、解析を継続 |
| `SINGLE-014` | ファイル名のIDとフロントマターの`id`の不一致 | check | failed／1 | `SPEC-FILE-NAME-001` |
| `SINGLE-015` | 文書ID重複 | check | failed／1 | `SPEC-ID-DUPLICATE-001`。新IDを提案しない |
| `SINGLE-016` | `approved`のREQに妥当な規範文が0件 | check | failed／1 | `SPEC-REQ-STATEMENT-001` |
| `SINGLE-017-01` | H1不一致 | check | failed／1 | `SPEC-STYLE-H1-001` |
| `SINGLE-017-02` | REQ必須H2欠落 | check | failed／1 | `SPEC-STYLE-SECTION-001` |
| `SINGLE-017-03` | ADR内の規範文 | check | failed／1 | `SPEC-STYLE-PLACEMENT-001` |
| `SINGLE-018-01` | H2順序違い | check | passed／0 | スタイルの診断を返さない |
| `SINGLE-018-02` | 空の任意節 | check | passed／0 | スタイルの診断を返さない |
| `SINGLE-018-03` | 疑似節 | check | passed／0 | スタイルの診断を返さない |
| `SINGLE-019` | UTF-8として復号できないファイル | check | failed／1 | `SPEC-INPUT-READ-001`、置換文字で継続しない |

### 6.3 関係とトレース

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-020` | 強い関係の参照先が不在 | check | failed／1 | `SPEC-RELATION-MISSING-001`だけ |
| `SINGLE-021` | 参照元／参照先の型不適合 | check | failed／1 | `CTX-RELATION-TYPE-001`。1エッジにつき主診断1件 |
| `SINGLE-022-01` | `requires`の禁止循環 | check | failed／1 | `CTX-CYCLE-001` |
| `SINGLE-022-02` | `refines`の禁止循環 | check | failed／1 | `CTX-CYCLE-001` |
| `SINGLE-022-03` | `related`の循環 | check | passed／0 | `CTX-CYCLE-001`を返さない |
| `SINGLE-023` | 旧`refs` | check | failed／1 | `SPEC-RELATION-LEGACY-001`。自動変換しない |
| `SINGLE-024` | `approved`文書の`implements`のパスが不在 | check | failed／1 | `SPEC-PATH-INVALID-001` |
| `SINGLE-025` | `draft`文書の未作成予定のパス | check | passed_with_warnings／0 | 同じコードが`warning` |
| `SINGLE-026` | 存在しない規範文への`covers` | check | failed／1 | `SPEC-TEST-COVERAGE-001` |
| `SINGLE-133` | 同じ`relations.requires`内に参照先の不在が2件 | check | failed／1 | `SPEC-RELATION-MISSING-001`が2件、`evidence`だけで区別できる |

### 6.4 基準版

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-027` | 禁止状態遷移 | check --base | failed／1 | `SPEC-STATE-TRANSITION-001` |
| `SINGLE-028` | 基準版に存在しない新規文書 | check --base | passed／0 | 現在値の語彙だけを検査 |
| `SINGLE-029` | 管理済みSPECの削除 | check --base | failed／1 | `SPEC-STATE-TRANSITION-001` |
| `SINGLE-030` | パスだけの変更 | check --base | passed／0 | `rename`として同一文書 |
| `SINGLE-031` | `approved`のREQの意味変更で状態を戻さない | check --base | failed／1 | `SPEC-SAFETY-APPROVED-001` |
| `SINGLE-032-01` | `implements`だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-032-02` | `tests`だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-032-03` | `related`だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-032-04` | `x-`拡張フィールドだけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-032-05` | 説明文だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-033` | 強い関係の参照先の変更 | check --base | passed_with_warnings／0 | `SPEC-IMPACT-OUTDATED-001` |
| `SINGLE-034` | 明示TASKの`src/`と`src2/` | check TASK-ID | failed／1 | `SPEC-TASK-BOUNDARY-001`、セグメント境界 |
| `SINGLE-035-01` | 引数なしの`check`でTASKが選ばれる | check | passed／0 | 境界未実施を`warning`にしない |
| `SINGLE-035-02` | `check --full`でTASKが選ばれる | check --full | passed／0 | 境界未実施を`warning`にしない |
| `SINGLE-036` | 解決できない`--base` | check | 結果なし／4 | 標準出力結果なし、レポートなし |
| `SINGLE-037` | Git不在時の引数なしの`check` | check | passed_with_warnings／0 | `SPEC-GIT-DEGRADED-001`、失われる保証を明示 |
| `SINGLE-038` | Git不在時の明示TASKの`check` | check TASK-ID | blocked／2 | `SPEC-TASK-BOUNDARY-002` |
| `SINGLE-039` | コミットのないリポジトリ | check | passed／0 | 全体検査、`revision: null` |
| `SINGLE-040` | 変更集合が空 | check | passed／0 | `selection`の3件数、実装前検査の代用にしない |
| `SINGLE-041` | どの逆索引にも該当しないコードまたはテストの変更 | check | passed／0 | 診断なし、件数だけ残す |

### 6.5 `context`とコンテキストのハッシュ値

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-042` | 固定入力の完全解決 | context | passed／0 | 正規JSONのバイト列と期待するハッシュ値が完全一致、2回の実行でも一致 |
| `SINGLE-043-01` | 固定起点を`--detail`付きで解決 | context --detail | passed／0 | `SINGLE-042`とハッシュ値、`resolution`が一致 |
| `SINGLE-043-02` | 固定起点を`--expand`付きで解決 | context --expand | passed／0 | `SINGLE-042`とハッシュ値、`resolution`が一致 |
| `SINGLE-044-01` | 本文の空行数だけを変更 | context | passed／0 | ハッシュ値が変化する |
| `SINGLE-044-02` | 表の桁揃えだけを変更 | context | passed／0 | ハッシュ値が変化する |
| `SINGLE-045` | `x-`拡張フィールドだけを変更 | context | passed／0 | ハッシュ値が変化しない |
| `SINGLE-046` | ハッシュ値が不一致の`--expect-digest` | context | blocked／2 | `CTX-STALE-001` |
| `SINGLE-047` | 解決集合外の`--expand` | context | failed／1 | `CTX-PROJECTION-001`、依存へ追加しない |
| `SINGLE-048-01` | 完全閉包が文書数上限超過 | context | blocked／2 | `CTX-LIMIT-001`、部分的なコンテキスト一式を返さない |
| `SINGLE-048-02` | 完全閉包がバイト上限超過 | context | blocked／2 | `CTX-LIMIT-001`、部分的なコンテキスト一式を返さない |
| `SINGLE-049` | 提示の絶対上限超過 | context | failed／1 | `CTX-PROJECTION-LIMIT-001` |
| `SINGLE-050` | 起点ID不在 | context | failed／1 | `CTX-ROOT-MISSING-001` |
| `SINGLE-051` | 先行TASKが未`done` | context --purpose implement | blocked／2 | `CTX-TASK-DEPENDENCY-001` |
| `SINGLE-052-01` | 起点が置換済み | context | blocked／2 | `CTX-STATE-SUPERSEDED-001`、後継へ差替えない |
| `SINGLE-052-02` | 依存先が置換済み | context | blocked／2 | `CTX-STATE-SUPERSEDED-001`、後継へ差替えない |
| `SINGLE-053` | 有効な後継が複数 | context | failed／1 | `CTX-STATE-SUPERSEDED-002` |
| `SINGLE-054` | `implement`対象の`MUST`が未`addressed` | context --purpose implement | passed_with_warnings／0 | `CTX-COVERAGE-TASK-001`、カバレッジ5区分 |

### 6.6 `verify`

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-055` | テスト成功 | verify | passed／0 | `targetResults[]`、`commands[]`が1件、`bindingId`が`<ws>::<name>` |
| `SINGLE-056` | テストの非0終了 | verify | failed／1 | `termination: exit`、`exitCode`が非0 |
| `SINGLE-057` | 実行ビット付きだがOSが拒否する実行形式 | verify | error／3 | 事前検査後の`spawn_error`、`SPEC-VERIFY-COMMAND-001`、空抜粋 |
| `SINGLE-058` | シグナル終了 | verify | error／3 | `termination: signal` |
| `SINGLE-059` | タイムアウト後も終了しない直接のプロセス | verify | error／3 | `SPEC-VERIFY-TIMEOUT-001`、強制終了、タイムアウト到達から5秒以内 |
| `SINGLE-060` | 対象の`MUST`が未`tested` | verify | blocked／2 | `CTX-COVERAGE-TEST-001`、テストを開始しない |
| `SINGLE-061` | コマンド名を解決できない | verify | blocked／2 | `SPEC-VERIFY-BLOCKED-001` |
| `SINGLE-062` | 引数なしで対象0件 | verify | blocked／2 | `SPEC-VERIFY-BLOCKED-002`、空CIを成功にしない |
| `SINGLE-063` | 2つの検証対象が同じコマンド名を要求 | verify | passed／0 | ハッシュ値2件、コマンドの実体1件、テストパスの重複排除 |
| `SINGLE-064` | 非成功の検証対象と通過した検証対象の混在 | verify | blocked／2 | 非成功は`bindingRefs: []`、通過分は実行 |
| `SINGLE-065` | `{tests}`なしのコマンドと複数のテストパス | verify | passed／0 | `argv`を1回だけ実行 |
| `SINGLE-066` | 規範文なしTECHの文書単位のテスト対応 | verify | passed／0 | `statements: []`でも`bindingRefs`を持つ |
| `SINGLE-067` | `cancelled`のTASK起点 | verify | blocked／2 | `CTX-STATE-001` |
| `SINGLE-068` | `done`のTASK起点 | verify | passed／0 | 再検証を許可 |
| `SINGLE-137` | 先行TASKが未完了（`open`）のTASK起点 | verify | blocked／2 | `CTX-TASK-DEPENDENCY-001`、`contextDigest: null`、`bindingRefs: []`、テストを開始しない |
| `SINGLE-138` | 先行TASKがすべて`done`のTASK起点 | verify | passed／0 | `CTX-TASK-DEPENDENCY-001`と`CTX-STATE-001`を返さない、先行TASKとその`addresses`の参照先を対象に加えない |
| `SINGLE-069-01` | 成功コマンドの標準出力／標準エラー出力が64 KiBを超える | verify | passed／0 | パイプを止めず、伏せ字化したUTF-8末尾65,536バイトと切り詰めフラグを保持 |
| `SINGLE-069-02` | 非0終了コマンドの標準出力／標準エラー出力が64 KiBを超える | verify | failed／1 | パイプを止めず、伏せ字化したUTF-8末尾65,536バイトと切り詰めフラグを保持 |

### 6.7 出力とレポート

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-070-01` | `--report`なしの成功`check` | check | passed／0 | ファイル生成0件、既存レポート不変 |
| `SINGLE-070-02` | `--report`なしの失敗`check` | check | failed／1 | ファイル生成0件、既存レポート不変 |
| `SINGLE-070-03` | `--report`なしの成功`verify` | verify | passed／0 | ファイル生成0件、既存レポート不変 |
| `SINGLE-070-04` | `--report`なしの失敗`verify` | verify | failed／1 | ファイル生成0件、既存レポート不変 |
| `SINGLE-071-01` | 明示`--report`付きの成功`check` | check | passed／0 | 規定先へ1件を排他的作成 |
| `SINGLE-071-02` | 明示`--report`付きの失敗`check` | check | failed／1 | 規定先へ1件を排他的作成 |
| `SINGLE-071-03` | 明示`--report`付きの成功`verify` | verify | passed／0 | 規定先へ1件を排他的作成 |
| `SINGLE-071-04` | 明示`--report`付きの失敗`verify` | verify | failed／1 | 規定先へ1件を排他的作成 |
| `SINGLE-072` | レポートの保存先が書込み不能 | check --report | error／3 | `SPEC-REPORT-WRITE-001`、元結果を端末へ保持 |
| `SINGLE-073-01` | `context`へ`--report` | context | 結果なし／4 | 未知オプションとして引数不正 |
| `SINGLE-073-02` | `doctor`へ`--report` | doctor | 結果なし／4 | 未知オプションとして引数不正 |
| `SINGLE-074-01` | 排他的オプションを同時指定 | check | 結果なし／4 | JSON本体なし、標準エラー1行、レポート0件 |
| `SINGLE-074-02` | 対象にコードのパスを指定 | verify | 結果なし／4 | JSON本体なし、標準エラー1行、レポート0件 |
| `SINGLE-074-03` | 対象に構文不正のIDを指定 | check | 結果なし／4 | JSON本体なし、標準エラー1行、レポート0件 |
| `SINGLE-075-01` | テキスト出力の成功 | check | passed／0 | 成功1行、JSONと同じ状態と件数 |
| `SINGLE-075-02` | テキスト出力の失敗 | check | failed／1 | 診断行の形式、JSONと同じ状態と件数 |
| `SINGLE-076` | 端末制御文字を含む失敗診断の要約とパス | check | failed／1 | 無害化して出力 |
| `SINGLE-077` | 同じ診断の条件を3か所で発生 | check | failed／1 | ワークスペース、パス、行、列、コード、`specRefs`の辞書順 |

### 6.8 上限

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-078` | `bitz.yaml` 64 KiB超 | check | failed／1 | `SPEC-INPUT-LIMIT-001`、読取りを続けない |
| `SINGLE-079-01` | SPEC Markdown 1 MiB超 | check | failed／1 | `SPEC-INPUT-LIMIT-001` |
| `SINGLE-079-02` | フロントマター32 KiB超 | check | failed／1 | `SPEC-INPUT-LIMIT-001` |
| `SINGLE-080-01` | 1文書の規範文と関係配列が`limit` | check | passed／0 | 境界内を誤遮断しない |
| `SINGLE-080-02` | 1文書の規範文が`limit + 1` | check | failed／1 | `SPEC-INPUT-LIMIT-001`だけを返す |
| `SINGLE-080-03` | 1文書の関係配列が`limit + 1` | check | failed／1 | `SPEC-INPUT-LIMIT-001`だけを返す |

### 6.9 診断レジストリ閉包

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-081` | `bitz.yaml`先頭の既存BOM | check | passed_with_warnings／0 | `SPEC-INPUT-BOM-001`、BOMを除いて解析継続 |
| `SINGLE-082` | SPEC Markdown先頭の既存BOM | check | passed_with_warnings／0 | `SPEC-INPUT-BOM-001`、フロントマターを解析継続 |
| `SINGLE-083` | `.spec/`内の未知ファイル | check | passed_with_warnings／0 | `SPEC-WORKSPACE-UNKNOWN-001`、SPECとして読まない |
| `SINGLE-084` | REQにTASK専用`changes` | check | passed_with_warnings／0 | `SPEC-FM-UNAVAILABLE-001`だけ |
| `SINGLE-085` | `x-`で始まらない未知のフロントマターフィールド | check | passed_with_warnings／0 | `SPEC-FM-UNKNOWN-001`だけ |
| `SINGLE-086` | フロントマターYAML構文不正 | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-01` | フロントマターのカスタムタグ | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-02` | フロントマターのアンカー | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-03` | フロントマターのエイリアス | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-04` | フロントマターのマージキー | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-05` | フロントマターの重複キー | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-088` | フロントマターフィールドの型不正 | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-089` | `SHOULD`の理由フィールドの欠如 | check | passed_with_warnings／0 | `EAI-CORE-SHOULD-001`だけ |
| `SINGLE-090` | `related`の参照先が不在 | check | passed_with_warnings／0 | `SPEC-RELATION-ADVISORY-MISSING-001`だけ |
| `SINGLE-091` | 設定の禁止YAML構文 | check | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ |
| `SINGLE-092` | 設定の型不正を`doctor`で検査 | doctor | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ。`doctor`固有の設定コードなし |
| `SINGLE-093` | 単一ワークスペースでGit不在 | doctor | passed_with_warnings／0 | `SPEC-DOCTOR-GIT-001`だけ |
| `SINGLE-094` | `.spec/bitz.yaml`不在 | check | blocked／2 | `SPEC-WORKSPACE-MISSING-001`だけ |
| `SINGLE-095` | 未知のEARS-AIメジャーバージョン | check | blocked／2 | `SPEC-EARS-VERSION-001`だけ |

### 6.10 EARS-AI文法、走査器、位置

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-096-01` | 1行に異なる長さを含む複数のコードスパン | context | passed／0 | 同じ連続数だけで閉じ、内部の構文解析器受入で完全な意味中間表現（`text`と`source`を含む）、公開JSONとハッシュ値を比較 |
| `SINGLE-096-02` | 開始と同じ連続数の終了の区切り文字なし | check | failed／1 | `EAI-CORE-SYNTAX-005`だけ、開始バッククォートの行／列 |
| `SINGLE-097-01` | テキストの`\[`、`\]`、`\\`、``\` ``、`\"` | context | passed／0 | 内部の構文解析器受入で各エスケープを1コードポイントへ解除した完全な意味中間表現、公開JSONとハッシュ値を比較 |
| `SINGLE-097-02` | 未知のエスケープ | check | failed／1 | `EAI-CORE-SYNTAX-004`だけ、バックスラッシュの行／列 |
| `SINGLE-098-01` | 未知の`quality`名前空間における、引用付き拡張タグの値の中のエスケープした`DQUOTE` | context | passed_with_warnings／0 | 内部の構文解析器受入で不透明な値を含む完全な意味中間表現、公開JSONとハッシュ値を比較 |
| `SINGLE-098-02` | 引用付き拡張タグの値が未閉鎖 | check | failed／1 | `EAI-CORE-SYNTAX-004`だけ、開始`DQUOTE`の行／列 |
| `SINGLE-099-01` | バッククォートのフェンス内の規範文のように見える文字列 | check | passed／0 | 候補を0件として扱う |
| `SINGLE-099-02` | チルダのフェンス内の規範文のように見える文字列 | check | passed／0 | 候補を0件として扱う |
| `SINGLE-099-03` | 引用ブロック内の規範文のように見える文字列 | check | passed／0 | 候補を0件として扱う |
| `SINGLE-099-04` | 半角スペース4個分の字下げによる規範文のように見える文字列 | check | passed／0 | 候補を0件として扱う |
| `SINGLE-100-01` | 短い既知接頭辞ID | check | failed／1 | 候補化し、`EAI-CORE-ID-001`だけ |
| `SINGLE-100-02` | 未知の大文字接頭辞ID | check | failed／1 | 候補化し、`EAI-CORE-ID-001`だけ |
| `SINGLE-100-03` | 3階層ID | check | failed／1 | 候補化し、`EAI-CORE-ID-001`だけ |
| `SINGLE-100-04` | `[ACTOR:...]`から始まるID欠落行 | check | failed／1 | 候補化し、`EAI-CORE-ID-001`だけ |
| `SINGLE-101-01` | `[SHOULD] [REASON] <text>` | context | passed／0 | 内部の構文解析器受入で`reason`を含む完全な意味中間表現、公開JSONとハッシュ値を比較 |
| `SINGLE-101-02` | `[MUST] [REASON] <text>` | check | failed／1 | `EAI-CORE-SYNTAX-001`だけ |
| `SINGLE-101-03` | `[MAY] [REASON] <text>` | check | failed／1 | `EAI-CORE-SYNTAX-001`だけ |
| `SINGLE-102` | マルチバイト文字とTABの後の不正なタグ | check | failed／1 | Unicodeコードポイント単位の1始まりの行／列を完全比較 |
| `SINGLE-103-01` | 未閉鎖のコードスパンと未閉鎖のタグが同じ`raw`に起因 | check | failed／1 | 主診断は`EAI-CORE-SYNTAX-005`だけ |
| `SINGLE-103-02` | 未閉鎖のタグとID形式不正が同じ`raw`に起因 | check | failed／1 | 主診断は`EAI-CORE-SYNTAX-004`だけ |

### 6.11 公開結果スキーマと既定表示

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-104-01` | `--format`省略の`context` | context | passed／0 | 標準出力は期待するMarkdownとバイト一致 |
| `SINGLE-104-02` | `--format`省略の`check` | check | passed／0 | 標準出力はテキスト |
| `SINGLE-104-03` | `--format`省略の`verify` | verify | passed／0 | 標準出力はテキスト |
| `SINGLE-104-04` | `--format`省略の`doctor` | doctor | passed／0 | 標準出力はテキスト、`scope=`なし |
| `SINGLE-105-01` | Gitありの`context`の`revision` | context | passed／0 | コミットは40桁の小文字16進 |
| `SINGLE-105-02` | Gitなしの`verify`の`revision` | verify | passed／0 | `revision: null` |
| `SINGLE-106-01` | コンテキスト一式の`full`提示 | context | passed／0 | `full`だけの必須フィールドと禁止フィールドをスキーマで検証 |
| `SINGLE-106-02` | コンテキスト一式の`normative`提示 | context | passed／0 | `normative`だけの必須フィールドと禁止フィールドをスキーマで検証 |
| `SINGLE-106-03` | `interpret`で起点を具体化する`draft`文書 | context | passed／0 | `advisory`を`reference`で提示し、必須フィールドと禁止フィールドをスキーマで検証 |
| `SINGLE-106-04` | 標準出力、標準エラー出力とも空の`verify`コマンド | verify | passed／0 | 空の抜粋、両方とも切り詰めフラグは`false` |
| `SINGLE-106-05` | 2つの検証対象に同じ診断の条件 | verify | failed／1 | テキストの`diagnostics`は両方の検証対象上の診断の総数 |
| `SINGLE-106-06` | `requires`の鎖で距離2以上のREQとTECH | context --purpose verify | passed／0 | 距離によらず役割`requirement`と`constraint`の文書を`full`で提示し、距離2の`MUST`の本文がコンテキスト一式に現れる |
| `SINGLE-106-07` | `SINGLE-107-01`と同じ起点を`--detail compact`で解決 | context --purpose verify --detail compact | passed／0 | 全文書を`reference`提示にし、コンテキストのハッシュ値を`--detail`省略時と同じ値にする |

### 6.12 共通の対象展開

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-107-01` | REQに具体化文書と`requires`の参照先がある | context --purpose verify | passed／0 | 具体化文書は対象規範文、`requires`の参照先はコンテキスト文書だけ |
| `SINGLE-107-02` | `SINGLE-107-01`と同じ起点 | verify | passed／0 | `context`と同じ対象規範文の集合 |
| `SINGLE-108-01` | 規範文ありTECHに具体化文書と`requires`の参照先がある | context --purpose verify | passed／0 | 4集合を完全比較 |
| `SINGLE-108-02` | `SINGLE-108-01`と同じ起点 | verify | passed／0 | `context`と同じ対象規範文の集合 |
| `SINGLE-109` | 規範文起点と同じ文書のほかの規範文 | context --purpose implement | passed／0 | 起点に指定した規範文と具体化文書は対象規範文、同じ文書のほかの規範文は隣接規範文 |
| `SINGLE-110` | TASKの`addresses`先と`requires`先のTASK | context --purpose verify | passed／0 | 自身の`addresses`先だけが対象規範文、`requires`先のTASKとその`addresses`先をコンテキスト文書へ含めない |
| `SINGLE-134` | 先行TASKがすべて`done`のTASKが、テスト対応のない`MUST`を`addresses`する | context --purpose implement | passed_with_warnings／0 | `CTX-STATE-001`と`CTX-TASK-DEPENDENCY-001`を返さない。先行TASKは役割`work`でコンテキストへ含め、対象規範文は対応済み・未テストで、`CTX-COVERAGE-TEST-001`が警告1件 |
| `SINGLE-135` | 起点の`refines`の参照先に、`requires`の鎖でも到達する（REQ-001が`requires`でREQ-002、`refines`でREQ-003、REQ-002が`requires`でREQ-003） | context --purpose implement | passed_with_warnings／0 | REQ-003は役割`refinement`（役割の表の上から最初に該当する行）で、その規範文は制約台帳にない。提示形式`normative`にせず`full`で提示し、`MUST`の本文がコンテキスト一式に現れる。`CTX-COVERAGE-TASK-001`が警告1件 |
| `SINGLE-136` | 文書単位で具体化した距離2の文書（REQ-001をTECH-002が、TECH-002をTECH-003が文書単位で`refines`する） | context --purpose interpret | passed／0 | 対象規範文と制約台帳が空なので、距離2のTECH-003は役割`refinement`でも`normative`にせず`full`で提示し、`MUST`の本文がコンテキスト一式に現れる |
| `SINGLE-111-01` | ワークスペースの仕様文書にない明示の文書ID | check | failed／1 | `CTX-ROOT-MISSING-001`、終了コード4ではない |
| `SINGLE-111-02` | 所有文書はあるが規範文IDが不在 | check | failed／1 | `CTX-ROOT-MISSING-001`、所有文書の`check`へ置換しない |
| `SINGLE-111-03` | ワークスペースに存在しない、構文上妥当な仕様文書のパス | check | failed／1 | `CTX-ROOT-MISSING-001`、終了コード4ではない |
| `SINGLE-111-04` | ワークスペースの仕様文書にない明示の文書ID | verify | failed／1 | 検証対象の診断に`CTX-ROOT-MISSING-001` |
| `SINGLE-112-01` | ADR起点 | context --purpose interpret | passed／0 | 対象規範文は空 |
| `SINGLE-112-02` | ADR起点 | context --purpose implement | 結果なし／4 | 標準出力結果なし、レポートなし |
| `SINGLE-112-03` | ADR起点 | check | passed／0 | 文書検査だけを行う |
| `SINGLE-112-04` | ADR起点 | verify | 結果なし／4 | 標準出力結果なし、レポートなし |
| `SINGLE-113` | 文書IDと同じ文書の規範文IDを複数指定 | verify | passed／0 | 起点、規範文、テスト割当てを各規定時点で重複排除 |
| `SINGLE-114` | `tests`のオブジェクト配列を持つREQ | check | passed／0 | フロントマタースキーマの正例、規範例との一致 |
| `SINGLE-115-01` | 最小REQフロントマター | check | passed／0 | REQの定義を通過 |
| `SINGLE-115-02` | 最小TECHフロントマター | check | passed／0 | TECHの定義を通過 |
| `SINGLE-115-03` | 最小ADRフロントマター | check | passed／0 | ADRの定義を通過 |
| `SINGLE-115-04` | `changes`省略の最小TASKフロントマター | check | passed／0 | TASKの定義を通過、許可パス0件 |
| `SINGLE-116-01` | `title`が120のUnicodeコードポイント | check | passed／0 | 境界値を受理 |
| `SINGLE-116-02` | `title`が121のUnicodeコードポイント | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-116-03` | `title`が空文字列 | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-116-04` | `title`が空白だけ | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-116-05` | `title`が改行を含む | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-117-01` | 必須フィールドの欠如 | check | failed／1 | `SPEC-FM-REQUIRED-001`だけ |
| `SINGLE-117-02` | Core標準フィールドが`null` | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-117-03` | `tests[].covers`が空配列 | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-118-01` | スカラー配列の重複 | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-118-02` | `covers`の順だけが異なる重複したテスト要素 | check | failed／1 | キーのタプルにより`SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-118-03` | 同じテストパスでコマンドまたは`covers`が異なる | check | passed／0 | 異なるテスト対応として受理 |
| `SINGLE-119-01` | `relations`内の未知キー | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-119-02` | `tests[]`内の未知キー | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-119-03` | 最上位の未知フィールド | check | passed_with_warnings／0 | `SPEC-FM-UNKNOWN-001`だけ |
| `SINGLE-119-04` | `x-`拡張フィールド | check | passed／0 | 値を保持し診断なし |
| `SINGLE-120-01` | TASK `changes: []`と変更差分なし | explicit TASK check | passed／0 | 省略と同じ許可パス0件 |
| `SINGLE-120-02` | `changes`省略TASKに変更差分あり | explicit TASK check | failed／1 | `SPEC-TASK-BOUNDARY-001`だけ |
| `SINGLE-120-03` | REQに正しい型の`changes` | check | passed_with_warnings／0 | `SPEC-FM-UNAVAILABLE-001`だけ |
| `SINGLE-120-04` | REQに型不正の`changes` | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ、利用不能の`warning`なし |
| `SINGLE-121` | Core 1.0の固定したハッシュ値の材料 | context | passed／0 | `digestVersion`と`resolverVersion`がともに`1.0` |
| `SINGLE-122` | 同一パスで`command`または`covers`が異なるテスト対応 | context | passed／0 | `(path, commandSortKey, covers)`の完全順序 |
| `SINGLE-123` | 同一の名前空間・`TERM`で値が異なる拡張タグ | context | passed_with_warnings／0 | `(namespace, term, valueSortKey)`の完全順序 |
| `SINGLE-124` | 非パス文字列と`argv`にバックスラッシュを含む | context --purpose verify | passed／0 | パス型フィールド以外のバックスラッシュを保持 |
| `SINGLE-125-01` | `context`のCore副作用 | context | passed／0 | リポジトリ、`HOME`、キャッシュ、一時ディレクトリへの書込み0件 |
| `SINGLE-125-02` | `doctor`のCore副作用 | doctor | passed／0 | リポジトリ、`HOME`、キャッシュ、一時ディレクトリへの書込み0件 |
| `SINGLE-125-03` | レポートなし`check`のCore副作用 | check | passed／0 | リポジトリ、`HOME`、キャッシュ、一時ディレクトリへの書込み0件 |
| `SINGLE-125-04` | 書込みなしコマンドによる`verify` | verify | passed／0 | テストプロセスを除くCore書込み0件 |
| `SINGLE-125-05` | 明示したレポート付き`check`のCore副作用 | check --report | passed／0 | 最終レポート1件だけ、一時ファイル残存0件 |
| `SINGLE-125-06` | `.spec/reports`がリポジトリ内ディレクトリへのシンボリックリンク | check --report | error／3 | `SPEC-REPORT-WRITE-001`、シンボリックリンク先の既存ファイル不変、一時ファイル残存0件 |
| `SINGLE-126-01` | `argv`要素が非文字列 | verify | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ、起動なし |
| `SINGLE-126-02` | `argv[0]`が空文字列 | verify | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ、起動なし |
| `SINGLE-126-03` | `argv`要素にNUL | verify | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ、起動なし |
| `SINGLE-126-04` | `argv`テンプレートが256要素超過 | verify | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ、起動なし |
| `SINGLE-126-05` | `argv`テンプレートの1要素が32 KiB超過 | verify | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ、起動なし |
| `SINGLE-126-07` | `argv[1:]`に空文字列 | verify | passed／0 | 空の1引数として変更せず渡す |
| `SINGLE-126-08` | `{tests}`展開後`argv`上限超過 | verify | blocked／2 | `SPEC-VERIFY-BLOCKED-001`、起動なし、`bindingRefs: []` |
| `SINGLE-126-09` | `PATH`上に実行ファイルがない | verify | blocked／2 | `SPEC-VERIFY-BLOCKED-001`、`spawn_error`にしない |
| `SINGLE-126-10` | 標準入力を読むコマンド | verify | passed／0 | nullデバイスから即時`EOF` |
| `SINGLE-126-11` | ロケールと任意の環境変数を読むコマンド | verify | passed／0 | 起動環境を継承し、`PWD`だけ実効の作業ディレクトリ |
| `SINGLE-126-12` | 子孫プロセスが標準出力／標準エラー出力のファイルディスクリプタを保持 | verify | error／3 | タイムアウト到達から5秒以内、`EOF`を待たない |
| `SINGLE-126-13` | タイムアウトしたテスト割当ての後に独立したテスト割当て | verify | error／3 | 後続のテスト割当てを実行して結果を保持 |
| `SINGLE-126-14` | 不正UTF-8、CR、ESC、C0／DEL／C1 | verify | passed／0 | U+FFFD、LF、`\\uNNNN`へ決定論的変換 |
| `SINGLE-126-15` | 環境の秘密情報と定型の秘密情報がチャンク境界をまたぐ | verify | passed／0 | 全対象を`[REDACTED]`へ置換し生値なし |
| `SINGLE-126-16` | 伏せ字化で公開文字列が64 KiB超 | verify | passed／0 | コードポイント境界での末尾保持、`raw`が上限内なら切り詰めフラグは`false` |
| `SINGLE-127-01` | `--format`を2回指定 | check | 結果なし／4 | 同じ値でも重複オプションとして操作開始前に拒否 |
| `SINGLE-127-02` | `--full`を2回指定 | check | 結果なし／4 | 重複フラグとして操作開始前に拒否 |
| `SINGLE-127-03` | 異なる`--expand`を反復 | context | passed／0 | 反復を受理し、正規ID辞書順 |
| `SINGLE-127-04` | 同じ`--expand`値を反復 | context | passed／0 | 1件へ重複排除 |
| `SINGLE-127-05` | 空文字列の明示対象 | check | 結果なし／4 | 引数なしの`check`へ置換しない |
| `SINGLE-127-06` | 起点0件の`context` | context | 結果なし／4 | 操作結果とレポートなし |
| `SINGLE-127-07` | `--workspace`の値が空文字列 | doctor | 結果なし／4 | オプション値の不足と同じく操作開始前に拒否 |
| `SINGLE-127-08` | `--timeout 0` | verify | 結果なし／4 | 下限外 |
| `SINGLE-127-09` | `--timeout 3601` | verify | 結果なし／4 | 上限外 |
| `SINGLE-127-10` | `--timeout +1` | verify | 結果なし／4 | 非正規の十進表記 |
| `SINGLE-127-11` | `--report=out.json` | check | 結果なし／4 | 未知オプション形式、任意のパスへ書かない |
| `SINGLE-127-12` | `--format json --report` | check | passed／0 | 両オプションを受理し、標準出力JSONと規定のレポートを生成 |
| `SINGLE-127-13` | ワークスペースの仕様文書にない構文上妥当な起点 | context | failed／1 | `CTX-ROOT-MISSING-001`、終了コード4ではない |
| `SINGLE-127-14` | カタログにない`--workspace` | doctor | 結果なし／4 | ワークスペース探索後、公開操作結果なし |
| `SINGLE-127-15` | Git 2.29を解決 | doctor | passed_with_warnings／0 | Git不在へ縮退し、下限値は詳細設計から取得 |
| `SINGLE-127-16` | Git 2.30を解決 | doctor | passed／0 | 下限境界を利用可能として扱う |
| `SINGLE-127-17` | Coreパッケージのメタデータ | package test | accepted／0 | 配布物、`import`パッケージ、CLI名は`bitz`、`requires-python`は3.12以上 |
| `SINGLE-127-18` | ビルドのメタデータとロックファイル | package test | accepted／0 | ランタイム依存は標準ライブラリと、厳密にロックしたYAMLライブラリ1つだけ |
| `SINGLE-127-19` | CPython 3.12でCoreを起動 | doctor | passed／0 | 3.12で利用できない構文／標準ライブラリのAPIへの依存なし |

### 6.13 規範文IDの文書一致と`local-id`の文法

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `SINGLE-128` | `approved`のREQ-001中の`[REQ-002:AC-01]` | check | failed／1 | `EAI-CORE-ID-001`、文書部分の不一致の要約 |
| `SINGLE-129` | `draft`のREQ-001中の`[REQ-002:AC-01]` | check | failed／1 | `EAI-CORE-ID-001`、`draft`でも重大度`error` |
| `SINGLE-130` | `local-id`の先頭が小文字の`[REQ-001:ac1]` | check | failed／1 | `EAI-CORE-ID-001`、形式不正の要約 |
| `SINGLE-131` | `local-id`に区切りのハイフンと数字がない`[REQ-001:AC1]` | check | failed／1 | `EAI-CORE-ID-001`、形式不正の要約 |
| `SINGLE-132` | `local-id`が複数のハイフンを含む`[REQ-001:A-B-01]` | check | passed／0 | ADR-054の境界を誤遮断しない |

## 7. 最小matrix: 複合ワークスペース

| fixture | 主な入力 | 操作 | 状態／終了コード | 必須確認 |
|---|---|---|---|---|
| `MULTI-001` | 別ワークスペースに同じローカルID | check all | passed／0 | 修飾IDで衝突しない |
| `MULTI-002-01` | 横断する`refines`と直接のカバレッジ | context | passed／0 | 修飾エッジ、カバレッジ、正規JSONとハッシュ値のgolden完全一致、2回の実行も一致 |
| `MULTI-002-02` | 横断する`refines`と直接のカバレッジ | verify | passed／0 | 修飾エッジ、ハッシュ値、カバレッジ |
| `MULTI-003` | 非修飾で別ワークスペースだけにある参照先 | check all | failed／1 | `SPEC-MULTI-REF-001`だけ |
| `MULTI-004-01` | `context`時に存在するワークスペース内の参照先が不在 | context | failed／1 | `SPEC-RELATION-MISSING-001`だけ |
| `MULTI-004-02` | `check`時に存在するワークスペース内の参照先が不在 | check | failed／1 | `SPEC-RELATION-MISSING-001`だけ |
| `MULTI-005` | 未知`--workspace` | check | 結果なし／4 | 標準出力結果なし、レポートなし |
| `MULTI-006` | Git既知の未登録設定 | check all | blocked／2 | `workspaces: []`、コマンドなし |
| `MULTI-007-01` | メンバーの入れ子 | doctor all | failed／1 | `SPEC-MULTI-PATH-001` |
| `MULTI-007-02` | メンバーがサブモジュール | doctor all | failed／1 | `SPEC-MULTI-PATH-001` |
| `MULTI-007-03` | メンバーが別ワークツリー | doctor all | failed／1 | `SPEC-MULTI-PATH-001` |
| `MULTI-008` | シンボリックリンクで別メンバーを所有 | check all | failed／1 | 所有境界のコード、TASKのコードなし |
| `MULTI-009` | `src/`と`src2/`のTASK変更 | explicit TASK check | failed／1 | セグメント境界 |
| `MULTI-010` | 基準版と現在版でシンボリックリンクのリンク先を変更 | explicit TASK check | failed／1 | 双方の所有判定 |
| `MULTI-011` | 1メンバーの文書が`failed`、後続メンバーは独立 | check all | failed／1 | 後続メンバーの件数を保持 |
| `MULTI-012` | 不正な文書に強く依存する検証対象 | verify all | failed／1 | 依存する検証対象は`blocked`、独立した検証対象は実行 |
| `MULTI-013` | 異なる2つのコンテキスト、共有するテスト割当て | verify all | passed／0 | ハッシュ値2件、コマンド1件 |
| `MULTI-014` | コマンド失敗後に独立したテスト割当てあり | verify all | failed／1 | 後続のテスト割当ても実行 |
| `MULTI-015` | 1メンバーだけ対象0件 | verify all | passed_with_warnings／0 | メンバーの`warning`、空配列 |
| `MULTI-016` | 複合ワークスペース全体で対象0件 | verify all | blocked／2 | 空CIを成功にしない |
| `MULTI-017` | IDを維持したメンバーのパス移動 | check all with base | passed／0 | 同一ワークスペース扱い |
| `MULTI-018-01` | メンバーのワークスペースID変更 | check all with base | failed／1 | 管理済みSPEC削除検査 |
| `MULTI-018-02` | メンバーの削除 | check all with base | failed／1 | 管理済みSPEC削除検査 |
| `MULTI-019` | Git不在 | doctor all | blocked／2 | `SPEC-MULTI-GIT-001` |
| `MULTI-020-01` | `memberCount = 99` | check all | passed／0 | 境界内を誤遮断しない |
| `MULTI-020-02` | `memberCount = 100` | check all | passed／0 | 境界値を誤遮断しない |
| `MULTI-020-03` | `specFileCount = 9,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MULTI-020-04` | `specFileCount = 10,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MULTI-020-05` | `inputBytes = 268,435,455` | check all | passed／0 | 境界内を誤遮断しない |
| `MULTI-020-06` | `inputBytes = 268,435,456` | check all | passed／0 | 境界値を誤遮断しない |
| `MULTI-020-07` | `statementCount = 99,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MULTI-020-08` | `statementCount = 100,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MULTI-020-09` | `relationEdgeCount = 999,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MULTI-020-10` | `relationEdgeCount = 1,000,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MULTI-020-11` | `traceEntryCount = 999,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MULTI-020-12` | `traceEntryCount = 1,000,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MULTI-020-13` | `commandDefinitionCount = 9,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MULTI-020-14` | `commandDefinitionCount = 10,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MULTI-020-15` | `verifyBindingCount = 9,999` | verify all | passed／0 | 境界内を誤遮断しない |
| `MULTI-020-16` | `verifyBindingCount = 10,000` | verify all | passed／0 | 境界値を誤遮断しない |
| `MULTI-021-01` | `memberCount = 101` | check all | blocked／2 | `dimension=memberCount`、`limit=100`、早期停止 |
| `MULTI-021-02` | `specFileCount = 10,001` | check all | blocked／2 | `dimension=specFileCount`、`limit=10000`、早期停止 |
| `MULTI-021-03` | `inputBytes = 268,435,457` | check all | blocked／2 | `dimension=inputBytes`、`limit=268435456`、早期停止 |
| `MULTI-021-04` | `statementCount = 100,001` | check all | blocked／2 | `dimension=statementCount`、`limit=100000`、早期停止 |
| `MULTI-021-05` | `relationEdgeCount = 1,000,001` | check all | blocked／2 | `dimension=relationEdgeCount`、`limit=1000000`、早期停止 |
| `MULTI-021-06` | `traceEntryCount = 1,000,001` | check all | blocked／2 | `dimension=traceEntryCount`、`limit=1000000`、早期停止 |
| `MULTI-021-07` | `commandDefinitionCount = 10,001` | check all | blocked／2 | `dimension=commandDefinitionCount`、`limit=10000`、早期停止 |
| `MULTI-021-08` | `verifyBindingCount = 10,001` | verify all | blocked／2 | `dimension=verifyBindingCount`、`limit=10000`、早期停止 |
| `MULTI-022-01` | 既定の複合ワークスペースの`check` | check all | passed／0 | レポートファイル0件 |
| `MULTI-022-02` | 明示`--report`付き複合ワークスペースの`check` | check all | passed／0 | 規定先へレポート1件 |
| `MULTI-022-03` | 既定の複合ワークスペースの`verify` | verify all | passed／0 | レポートファイル0件 |
| `MULTI-022-04` | 明示`--report`付き複合ワークスペースの`verify` | verify all | passed／0 | 規定先へレポート1件 |
| `MULTI-023-01` | 単一ワークスペースのJSON | consumer test | accepted／0 | 単一外形として受理 |
| `MULTI-023-02` | 複合ワークスペースのJSON | consumer test | accepted／0 | 複合ワークスペース外形として受理 |
| `MULTI-023-03` | 単一／複合ワークスペースのフィールドが混在するJSON | consumer test | rejected／1 | 排他的外形として拒否 |
| `MULTI-024-01` | 複合ワークスペース形式への移行 | migration test | passed／0 | 原子的に切り替える |
| `MULTI-024-02` | 完全なロールバック | migration test | passed／0 | 旧形式へ完全に戻る |
| `MULTI-024-03` | 部分的なロールバック | migration test | rejected／1 | 部分的なロールバックを拒否 |
| `MULTI-025-01` | 存在するワークスペースの、不在の修飾起点 | check | failed／1 | `CTX-ROOT-MISSING-001`、未知`--workspace`と区別 |
| `MULTI-025-02` | 存在するワークスペースの、不在の修飾起点 | verify | failed／1 | 検証対象の診断に`CTX-ROOT-MISSING-001` |
| `MULTI-026-01` | カタログの事前検査を通過するルートワークスペースと2つのメンバー | doctor all | passed／0 | ルートワークスペースが先頭・メンバーID順、ワークスペースに依存しない検査項目とメンバーの検査項目を分離 |
| `MULTI-026-02` | 1つのメンバーのコマンドが不在 | doctor all | blocked／2 | 後続メンバーを継続、メンバーの診断と全体の状態を集約、テキストの件数 |

`MULTI-012`では、不正な文書を所有するメンバーを`failed`、それを必要とする検証対象を
`SPEC-MULTI-DEPENDENCY-001`／`blocked`、独立した検証対象を通過とし、最上位は最悪値の`failed`に固定する。

## 8. 性能fixture

性能は適合fixtureとは別に、[品質属性と安全境界 §4](../../02.設計書/02_品質属性と安全境界.md#4-性能予算)の
基準fixtureと環境マニフェストで測定する。測定条件は、クリーンな作業ツリー、マニフェストに固定したストレージの種類（`storageClass`）、
ネットワークなし、`--report`なし、JSON出力、Coreの永続キャッシュなし、OSのファイルキャッシュを1回暖機した後の5回の中央値とする。
WSL2では、仮想ディスクを、ゲストから観測できない物理SSDとして推定しない。
性能fixtureはmatrixへ含めず、回帰検査として独立に運用する。

基準入力は、リポジトリのルートの[`fixtures/performance`](../../../fixtures/performance/README.md)に置く。バージョン管理した
データセットのマニフェスト、生成器のバージョン、期待する木構造のハッシュ値の3つが一致した生成した木構造だけを測定へ使用する。単一ワークスペースは
300 SPEC／1,000規範文／5,000関係、複合ワークスペースは20ワークスペース／1,000 SPEC／20,000関係とする。
測定するケース、固定したSLO、基準となる環境、観測結果のフィールドは、同じディレクトリのJSONを正とする。基準の比較キーと
一致しない実行は`not_comparable`であり、性能ゲートの成功または失敗へ数えない。

人間による完了時間、仕様記述時間、レビュー時間、欠陥検出数は、
[`fixtures/comparison`](../../../fixtures/comparison/README.md)のプロトコル、5件の比較タスク、非公開の正解表で
任意に測定できる。この測定はCoreのプロセスの実時間またはメモリの結果へ混ぜず、Core 1.0のGate Cまたは
リリースの条件にしない。有効な結果を取得するまでは、人の生産性に対する優位性を主張しない
（[ADR-058](../../02.設計書/10_決定記録/ADR-058_Gate-Cから比較タスクの実測を外す.md)）。

`limit + 1`の絶対上限のfixtureは性能SLOの対象ではなく、安全な停止だけを検査する。
