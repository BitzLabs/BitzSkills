# Core 1.0の性能fixture

## 1. 目的

本ディレクトリは、再現できる性能の入力と測定基準を所有する。性能fixtureは適合fixtureではない。回帰を検出し、
`docs/02.設計書/02_品質属性と安全境界.md`の予算を守らせるが、新しい機能上の意味は加えない。

生成した木構造は、重複した数千件のMarkdownファイルとしてはコミットしない。バージョン管理したデータセットのマニフェスト、
`scripts/generate_fixture.py`、`expectedTreeDigest`をfixtureとする。生成した木構造は、件数とハッシュ値が
マニフェストと一致する場合だけ受け入れる。

## 2. データセット

`datasets/*.json`は`schemas/dataset.schema.json`、`environments/*.json`は`schemas/environment.schema.json`、
`benchmark-plan.json`は`schemas/benchmark-plan.schema.json`、測定結果は`schemas/run-result.schema.json`で検証する。

| データセット | 固定した形状 | ベンチマークの対象 |
|---|---|---|
| `core-single-v1` | 仕様文書300件、規範文1,000件、関係5,000件 | 変更範囲の`check`、全体の`check`、`doctor`、20文書の`context`、`verify`のオーバーヘッド |
| `core-multi-workspace-v1` | ワークスペース20件、仕様文書1,000件、規範文1,000件、関係20,000件 | `--all-workspaces`の`check`、3ワークスペース・20文書の`context` |

新しい、または空の出力先へ生成し、表示されたハッシュ値を確認する。

```text
python3 fixtures/performance/scripts/generate_fixture.py fixtures/performance/datasets/core-single-v1.json <output>
python3 fixtures/performance/scripts/generate_fixture.py fixtures/performance/datasets/core-multi-workspace-v1.json <output>
```

木構造のハッシュ値は、相対パスのUnicodeのコードポイント辞書順に並べたファイルに対するSHA-256である。各ファイルのハッシュ値の入力は、UTF-8の
相対パス、NUL、符号なし8バイトのビッグエンディアンによる内容の長さ、ファイルのバイト列の順とする。ディレクトリ、権限、時刻は
含めない。生成するテキストはBOMなしのUTF-8で、改行はLFとする。

## 3. 測定手順

手順の正本は`benchmark-plan.json`とする。各ケースは、受け入れた木構造から作った一時的なGitのリポジトリで、新しい
プロセスとして実行する。基準版はクリーンなコミットとし、`changed-check`だけが、基準のコミットの後、測定の前に、
マニフェストの`changedAppendUtf8`のバイト列を`changedPath`へ追記する。

- 基準環境は`environments/core-1-reference.json`とし、観測値は`schemas/run-result.schema.json`に従って記録する。
- ネットワーク接続を無効にする。マニフェストのストレージの種類、`--format json`を使い、`--report`とCoreの永続的なキャッシュは使わない。
  基準環境のWSL2の仮想ディスクを、ゲストから観測できない物理SSDとして推定しない。
- 測定しない暖機を1回行った後、測定する実行を5回逐次に行う。単調に増加する時計を使い、各値と中央値を記録する。
- 初回の実行の経過時間は別に記録する。各`peakRssBytes`は、プロセスの起動の直前の、隔離したcgroup v2のスコープを基準とする、
  Linuxのプロセスの木構造全体のピークRSSの増分である。5回の値とその最大値を記録する。
- 比較キーが異なる実行は`not_comparable`とする。観測データとして残してよいが、ゲートの合否には使わない。
- 比較できる実行は、固定した経過時間とメモリの予算をすべて満たす場合だけ合格とする。回帰の比較は、最初に
  受け入れたベースラインができるまでは参考とし、その後は10パーセントと絶対的な誤差の許容の両方を超えて悪化した指標を不合格とする。
- 絶対上限の`limit ± 1`のfixtureは、適合と安全性の試験に属し、通常の200 MiBの性能ゲートには含めない。

`verify`のオーバーヘッドは、同じ生成した木構造と5回の測定の手順を使った`median(verifyの経過時間) - median(何もしないcommandの経過時間)`
とする。負の値は0として記録する。両方の系列と、導いた値を残す。

測定の前に、基準環境と隔離の機能だけを検査できる。

```text
uv run fixtures/performance/run_benchmarks.py probe
```

コミット済みのクリーンな作業ツリーから全ケースを逐次に測定し、結果のスキーマに適合するJSONを作る。

```text
uv run fixtures/performance/run_benchmarks.py run --output /tmp/bitz-performance.json
```

ランナーは、ユーザーのsystemdのルートスライス直下にケースごとの一時ユニットを作り、プライベートネットワークと、cgroup v2の
プロセスの木構造全体を隔離する。ユニットと一時ディレクトリは、各実行が終わるたびに回収する。

## 4. 結果の所有

受け入れたベースラインの結果は`fixtures/performance/baselines/<environment-id>/<core-commit>.json`に置く。実行できる
Coreができるまで、ベースラインの結果は作らない。データセット、環境の比較キー、測定の規則、受け入れたベースラインを更新する場合は、
同じ変更でレビューを受ける。測定結果を黙って書き換えない。

初回のベースラインは、`core-1-linux-wsl2-ryzen-9-9900x`の環境でCoreのコミット
`4b3d95982e33bf77486068df57faf3111a1c1152`を測定した結果である。`validate_benchmarks.py`は、
ベースラインのスキーマ、パスの環境IDとコミット、そのコミットが現在の`HEAD`の祖先であること、観測環境の比較キー、
データセットのハッシュ値、ケースの集合と順序、中央値・最大RSS・`verify`のオーバーヘッドの再計算、固定したSLOを検査する。
`status: passed`という自己申告だけでは監査を通過しない。新しいベースラインを追加するときも、同じ監査の対象になる。

## 5. 入力の形状とStep 0-Pの検証

`shape`は、生成した`.spec/requirements/REQ-*.md`だけを測る（フロントマターを含むUTF-8のバイト数）。
`specBytes`はその合計のバイト数、`meanSpecBytes`はそれを仕様文書の件数Nで割った値、`statementsPerSpec`は規範文の件数を
Nで割った値である。`edgeDensity`は有向の関係の件数Eを N × (N − 1) で割った値で、自己参照のエッジを除き、
複合ワークスペース全体でワークスペースを越えるエッジを含む。
比は約分しない整数の分子と分母で保持する。すべての値は完全な一致を要求し、許容誤差を設けない。
コンテキストの文書数とワークスペース数は、生成器が別に検査する。入力のバイト数は、Coreが最終的に提示するバイトの予算を
証明しない。それはCoreの実装の後に測定する。

CPython 3.11以上と`uv`がある新しいチェックアウトで、次を実行する。

```text
uv run fixtures/validate_benchmarks.py
```

このスクリプトは、検証用の依存を固定し、入力のJSONとすべてのスキーマ（将来の結果のスキーマを含む）を検証し、参照を検査し、
各データセットを2回生成して件数、形状、ハッシュ値を比べ、壊した形状の期待値が拒否されることを確認する。
初回はパッケージのダウンロードが必要である。依存がキャッシュされていれば、以後は`uv run --offline`でオフラインで実行できる。
Coreができるまで測定結果を作らない。このコマンドはStep 0-Pを担い、将来のStep 0B全体の入口の1つになる。

## 6. 対象外

性能と比較の手順は、MCP、実際のプロファイル、提示内容のハッシュ値、フォーマッター／スタイルのリンター、ID改番の支援、
より細かいテストを選ぶ指定をCore 1.0の受入から除く。
10,000件の仕様文書のケースと、`limit ± 1`の絶対上限のケースは、適合と安全性の試験に属し、通常の性能SLOには含めない。
