# Step 0-P検証記録

- 日付: 2026-09-07
- 結果: `Passed`
- command: `uv run fixtures/validate_step0p.py`
- 検証環境: CPython 3.14.4、Linux。依存はscriptのmetadataで固定した。
- 範囲: 性能・比較の入力の準備。Coreの性能baselineでも、Gate Aの承認でもない。

| 検査 | 結果 |
|---|---|
| Draft 2020-12 Schemaの構造 | 将来使う結果Schema 2件を含む8件が通過 |
| dataset、環境、計画、task、protocol、正解表の入力 | JSON入力11件が通過 |
| benchmarkのdataset・環境の参照とtask一覧 | 通過 |
| 単一workspaceのdataset生成 | 2回の生成が一致: SPEC 300件、規範文1,000件、関係5,000件 |
| 複合workspaceのdataset生成（当時の名称はfederation） | 2回の生成が一致: workspace 20件、SPEC 1,000件、規範文1,000件、関係20,000件 |
| 形状の期待値 | byte数、SPECあたりの規範文数、有向edge密度が一致 |
| 形状を壊した期待値 | 両datasetとも拒否 |
| Context入力の閉包 | generatorが20文書、1／3 workspace、入力byte予算を確認 |

期待tree digestは変わらなかった。

- 単一workspace: `sha256:0693e6ec926d4a411766796831e87c011004342810a5e6f3393e7afcd52c546c`
- 複合workspace（当時の名称はFederation）: `sha256:ad519b9442984ab9bce488ba1aa05277e9077bad178f89378a90e5f458134c25`

検証環境は、性能の基準環境（CPython 3.11.x）とは別である。
Coreの出力サイズ、性能baseline、参加者の観測値は、該当するCore実装ができるまで保留する。
Step 0Bには適合fixtureと、fresh checkoutから全体を検証するcommandがまだ必要である。Step 0-Pの完了だけではGate Aを開かない。

## 2026-09-17: 複合workspaceの識別子の改名

ADR-047に従い、dataset `core-federation-v1`を`core-multi-workspace-v1`、種別`federation`を`multiWorkspace`、
benchmark case `federation-full-check`・`federation-context-20`を`multi-workspace-full-check`・
`multi-workspace-context-20`へ改名した。generatorが書き出す設定keyも`monorepo`から`multiWorkspace`へ改めた。

旧generatorと新generatorの生成物を比べ、差分は`.spec/bitz.yaml`の設定key 1行だけであることを確認した。
件数、SPECのbyte数、edge密度は変わらない。新generatorでの生成2回は一致した。

- 単一workspace: `sha256:0693e6ec926d4a411766796831e87c011004342810a5e6f3393e7afcd52c546c`（不変）
- 複合workspace: `sha256:1626b4d08eb9a05e8cdeef71f125292dfc71495f175119c6f99bd76c5b837a54`（旧`sha256:ad519b94…`から更新）
