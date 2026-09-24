# Core 1.0の性能fixture

## 1. 目的

本directoryは、再現できる性能の入力と測定基準を所有する。性能fixtureは適合fixtureではない。回帰を検出し、
`docs/02.設計書/02_品質属性と安全境界.md`の予算を守らせるが、新しい機能上の意味は加えない。

生成したtreeは、重複した数千件のMarkdown fileとしてはcommitしない。version管理したdatasetのmanifest、
`scripts/generate_fixture.py`、`expectedTreeDigest`をfixtureとする。生成したtreeは、件数とdigestがmanifestと
一致する場合だけ受け入れる。

## 2. dataset

`datasets/*.json`は`schemas/dataset.schema.json`、`environments/*.json`は`schemas/environment.schema.json`、
`benchmark-plan.json`は`schemas/benchmark-plan.schema.json`、測定結果は`schemas/run-result.schema.json`で検証する。

| dataset | 固定した形状 | benchmarkの対象 |
|---|---|---|
| `core-single-v1` | SPEC 300件、規範文1,000件、関係5,000件 | 変更範囲のcheck、全体check、doctor、20文書のcontext、verifyのoverhead |
| `core-multi-workspace-v1` | workspace 20件、SPEC 1,000件、規範文1,000件、関係20,000件 | `--all-workspaces`のcheck、3 workspace・20文書のcontext |

新しい、または空の出力先へ生成し、表示されたdigestを確認する。

```text
python3 fixtures/performance/scripts/generate_fixture.py fixtures/performance/datasets/core-single-v1.json <output>
python3 fixtures/performance/scripts/generate_fixture.py fixtures/performance/datasets/core-multi-workspace-v1.json <output>
```

tree digestは、相対pathのUnicodeコードポイント順に並べたfileに対するSHA-256である。各fileのhash入力は、UTF-8の
相対path、NUL、符号なし8 byteのbig-endianによる内容の長さ、fileのbyte列の順とする。directory、権限、時刻は
含めない。生成するtextはBOMなしのUTF-8で、改行はLFとする。

## 3. 測定手順

手順の正本は`benchmark-plan.json`とする。各caseは、受け入れた生成treeから作った一時Git repositoryで、新しい
processとして実行する。基準版はcleanなcommitとし、`changed-check`だけが基準commitの後、測定の前に、
manifestの`changedAppendUtf8`のbyte列を`changedPath`へ追記する。

- 基準環境は`environments/core-1-reference.json`とし、観測値を`schemas/run-result.schema.json`で記録する。
- network接続を無効にする。local SSD、`--format json`を使い、`--report`とCoreの永続cacheは使わない。
- 測定しない暖機を1回行った後、測定する実行を5回逐次に行う。単調時計を使い、各値と中央値を記録する。
- 初回実行の経過時間は別に記録する。各`peakRssBytes`は、process起動直前の隔離したcgroup v2 scopeを基準とする、
  Linuxのprocess tree全体のpeak RSSの増分である。5回の値とその最大値を記録する。
- 比較keyが異なる実行は`not_comparable`とする。観測データとして残してよいが、gateの合否には使わない。
- 比較できる実行は、固定した経過時間とmemoryの予算をすべて満たす場合だけ合格とする。回帰の比較は、最初に
  受け入れたbaselineができるまでは参考とし、その後は10 percentと絶対的な誤差許容の両方を超えて悪化した指標を不合格とする。
- hard limitの`limit ± 1` fixtureは適合・安全性の試験に属し、通常の200 MiBの性能gateには含めない。

verifyのoverheadは、同じ生成treeと5回の測定手順を使った`median(verifyの経過時間) - median(何もしないcommandの経過時間)`
とする。負の値は0として記録する。両方の系列と、導いた値を残す。

## 4. 結果の所有

受け入れたbaselineの結果は`fixtures/performance/baselines/<environment-id>/<core-commit>.json`に置く。実行できる
Coreができるまで、baselineの結果は作らない。dataset、環境の比較key、測定規則、受け入れたbaselineを更新する場合は、
同じ変更でreviewを受ける。測定結果を黙って書き換えない。

## 5. 入力の形状とStep 0-Pの検証

`shape`は、生成した`.spec/requirements/REQ-*.md`だけを測る（Frontmatterを含むUTF-8のbyte数）。
`specBytes`はその合計byte数、`meanSpecBytes`はそれをSPEC件数Nで割った値、`statementsPerSpec`は規範文の件数を
Nで割った値である。`edgeDensity`は有向の関係件数Eを N × (N − 1) で割った値で、自己参照のedgeを除き、
複合workspace全体でworkspaceを越えるedgeを含む。
比は約分しない整数の分子と分母で保持する。すべての値は完全一致を要求し、許容誤差を設けない。
Contextの文書数とworkspace数は、generatorが別に検査する。入力のbyte数は、Coreが最終的に提示するbyte予算を
証明しない。それはCoreの実装後に測定する。

CPython 3.11以上と`uv`があるfresh checkoutで、次を実行する。

```text
uv run fixtures/validate_benchmarks.py
```

このscriptは検証用の依存を固定し、入力JSONとすべてのSchema（将来の結果Schemaを含む）を検証し、参照を検査し、
各datasetを2回生成して件数・形状・digestを比べ、壊した形状の期待値が拒否されることを確認する。
初回はpackageのdownloadが必要である。依存がcacheされていれば、以後は`uv run --offline`でoffline実行できる。
Coreができるまで測定結果を作らない。このcommandはStep 0-Pを担い、将来のStep 0B全体の入口の1つになる。

## 6. 対象外

性能と比較の手順は、MCP、実際のProfile、Projection Digest、formatter／style linter、ID改番の支援、
より細かいtest selectorをCore 1.0の受入から除く。
10,000 SPECと`limit ± 1`のhard limitのcaseは適合・安全性の試験に属し、通常の性能SLOには含めない。
