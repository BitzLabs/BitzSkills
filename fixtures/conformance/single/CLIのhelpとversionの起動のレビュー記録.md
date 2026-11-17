# CLIの`--help`と`--version`の起動のfixtureのレビュー記録

## 2026-11-17の追加（ADR-075）

[ADR-075](../../../docs/02.設計書/10_決定記録/ADR-075_CLIへ--helpと--versionを加える.md)と
[Core実行環境・CLI基盤契約 §5.1](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#51---helpと--version)、
[結果・診断・終了コード §3](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md#3-結果の状態と終了コード)を根拠に、
CLIの引数の境界の群の続きとして`SINGLE-127-20`〜`46`の27件を加えた。生成と監査は`help_version_fixtures.py`が行う。CoreのCLIは実装も実行もしない。

| ID | 引数列 | 入力 | 期待 | 根拠 |
|---|---|---|---|---|
| `SINGLE-127-20` | `--help` | ワークスペース | 0、`--help`の出力 | §5.1の表の1行目 |
| `SINGLE-127-21` | `--help --no-such-option` | 同上 | 同上 | 同上（後に続く要素は見ない） |
| `SINGLE-127-22` | `--help --version` | 同上 | 同上 | 同上。`--version`の1要素の条件に当たらない |
| `SINGLE-127-23`〜`26` | `check`、`context`、`verify`、`doctor`の`--help` | 同上 | 同上 | §5.1の表の2行目 |
| `SINGLE-127-27` | `check --no-such-option --help` | 同上 | 同上 | §5.1の1つ目の箇条（未知のオプションより優先） |
| `SINGLE-127-28` | `verify REQ-001 --help --timeout` | 同上 | 同上 | 同上（値の不足より優先） |
| `SINGLE-127-29` | `context REQ-001 --purpose --help` | 同上 | 同上 | §5.1の表の2行目（2番目以降の「いずれかの要素」が完全に一致する） |
| `SINGLE-127-30` | `check --full --full --help` | 同上 | 同上 | §5.1の1つ目の箇条（重複より優先） |
| `SINGLE-127-31` | `check "" --help` | 同上 | 同上 | 同上（空文字列の位置引数より優先。§5） |
| `SINGLE-127-32` | `doctor --help --help` | 同上 | 同上 | §5.1の1つ目の箇条（`--help`自身の反復を重複にしない） |
| `SINGLE-127-33` | `foo --help` | 同上 | 4、未知の操作 | §5.1の2つ目の箇条 |
| `SINGLE-127-34` | `--version` | 同上 | 0、`bitz 1.0.0`とLF | §5.1の表の3行目と4つ目の箇条 |
| `SINGLE-127-35` | `--version check` | 同上 | 4、未知の操作 | §5.1の3つ目の箇条 |
| `SINGLE-127-36` | `check --version` | 同上 | 4、`check`の未知のオプション | 同上 |
| `SINGLE-127-37` | `--version --version` | 同上 | 4、未知の操作 | 同上（1要素だけに限る） |
| `SINGLE-127-38` | `check --help=1` | 同上 | 4、`check`の未知のオプション | §5.1の表の2行目（完全に一致しない）と§5（`--name=value`形式を受け付けない） |
| `SINGLE-127-39`、`40` | `--help`、`--version` | `.spec/bitz.yaml`のないGitのリポジトリ | 0 | §5.1の前文（ワークスペースの外でも同じ） |
| `SINGLE-127-41`、`42` | `doctor --help`、`--version` | `.spec/bitz.yaml`がなく、Gitのリポジトリでもないディレクトリ | 0 | 同上 |
| `SINGLE-127-43`、`44` | `check --help`、`--version` | YAMLの構文が不正な設定（`SINGLE-170-01`と同じ設定） | 0 | §5.1の前文（設定とファイルの読取りを行わない） |
| `SINGLE-127-45`、`46` | `check --format json --report --help`、`verify REQ-001 --report --help` | ワークスペース | 0、レポート0件 | §5.1の前文（レポートを作らない） |

- 入力のワークスペースは`SINGLE-042`のcorpus（`cli_error_fixtures.py`と同じ。Gitのリポジトリで、コミットなし）である。ワークスペースの外の4件は、
  同じcorpusから`.spec/`の下を除いたもので、`SINGLE-127-41`・`42`は`setup.git: false`（Gitの状態は明示的な不在の`null`）とする。
- 27件すべて、マニフェストの`expect`は`{"exitCode": 0 または 4, "stdout": "none", "reportFileCount": 0}`で、結果の状態と期待結果のファイルを持たない。
  副作用の期待値は、リポジトリ、`git status`とGitのインデックス、隔離した`HOME`・キャッシュ・`TMPDIR`の前後の完全一致（読取り専用）とする。
  ファイルを作らないこと（ワークスペースの外で`.spec/`を作らないことを含む）と、`.spec/reports/`にレポートを作らないことは、この比較が固定する。
  ファイルを読まないことは外から観測できないので、構文が不正な設定でも終了コード0になること（`SINGLE-127-43`・`44`）で固定する。
- `--help`の出力（`cli-output.json`の`{"exitCode": 0, "stdoutNonEmptyText": true, "stderrLineCount": 0}`）は、標準出力が空でなく、UTF-8で、
  改行で終わり、標準エラー出力が空であることだけを比べる（§5.1の最後の箇条。文言、行の構成、並びは契約にしない）。
- `--version`の出力（`{"exitCode": 0, "stdout": "bitz 1.0.0\n", "stderrLineCount": 0}`）は、標準出力のバイト列の完全一致と、空の標準エラー出力を比べる。
  値`1.0.0`は、`doctor`の結果の`core.version`（§5.1の4つ目の箇条）で、レビュー済みの`doctor`のfixtureの期待結果から読む。監査は、単一と複合の
  すべての`doctor`の期待結果の`core.version`が同じ1つの値であることを確かめる。
- 終了コード4の出力は、既存の引数不正のfixtureと同じ`cli-output.json`（標準出力は空、標準エラー出力は空でない理由を持つ1行、端末の制御文字なし）である。
  最初の要素が公開の操作の名前の場合（`SINGLE-127-36`・`38`）は、既存の未知のオプションのfixture（`SINGLE-073-*`、`SINGLE-127-11`）と同じく接頭辞を`bitz: check: `とする。
  最初の要素が公開の操作の名前でない場合（`SINGLE-127-33`・`35`・`37`）は、結果・診断・終了コード §3の`<operation-or-argv-context>`に何を書くかを
  仕様が定めないので、接頭辞を`bitz: `とし、残りが空でないことだけを比べる。

### harnessの変更

従来の`cli-output.json`は終了コード4の出力だけを表し、マニフェストのスキーマは終了コード0の起動に結果の状態（`status`）を要求していた。
§5.1の2つの起動は結果を作らずに終了コード0で終わり、`--help`の標準出力は文言を契約にしないので、従来の比較では表せなかった。次の最小の変更を加えた。
既存のfixtureの比較は変えず、比較の範囲を広げていない。

- `manifest.schema.json`: `stdout: none`で終了コード0の起動を許す。この場合は、終了コード4と同じく`status`、`outcome`、`resultFile`、`resultDigest`、
  `textFile`を持てない。`outcome`を必須とする`bitz`以外のランナーでは成り立たない。
- `runner.py`: `cli-output.json`の標準出力の比べ方に`stdoutNonEmptyText: true`（UTF-8で、空でなく、改行で終わる）を加え、`stdout`（バイト列の完全一致）と
  どちらか一方だけを持つことを検査する。`stderrLineCount: 0`は空の標準エラー出力を要求し、行の形のキーを持たない。形の誤った`cli-output.json`はfixtureのエラーとする。
- `fake_core.py`: 偽のCoreが、`stdout: none`の起動でも`cli-output.json`の標準出力を書くようにした（harnessの自己試験用）。

### 監査

`help_version_fixtures.py`は、マニフェスト、`cli-output.json`、入力のバイト列、副作用のスキーマと内容を照合し、各fixtureを隔離環境で2回準備して
固定したスナップショットと一致させる。引数列から§5.1の条件で期待の種類（`--help`、`--version`、未知の操作、未知のオプション）を導き直し、
説明だけを変えた改変を拒否する。harnessの比較（`runner._check_cli_output`）を、各fixtureの期待値で陽性と陰性の対照に当てる
（空の標準出力、改行のない出力、不正なUTF-8、空でない標準エラー出力、違う終了コード、`--version`の1行の空白と改行の違いを拒否する）。
これは期待値の破損の検出であり、Coreが実際に起動を扱った証拠ではない。CoreはStep 1のGate Bで検証する。
