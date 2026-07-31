# M0 eval — 3プラットフォーム実測 harness

`FLW-DSN-014` の M0 eval protocol を実行するための道具一式。
**本ディレクトリは harness であり、実測結果はまだ含まれていない**（`status: not-measured`）。

## なぜ M0 で測るのか

M0 の主目的は「単一 dispatcher にすると、エージェントが生コマンドへ迂回せず、
3プラットフォームで同じ判断へ収束するか」を write 機能を作る前に実証することである。
ここで閾値を満たさなければ、文章を長くするのではなく **description・入口名・schema・
renderer を直して M0 を再実行する**（`FLW-DSN-010`）。

## 固定条件

| 項目 | 値 |
|---|---|
| platforms | Claude Code / Codex CLI / Antigravity 2.0 |
| conditions | skill なし / v1 skill / v2 skill fixture |
| tasks | `repo-inspect` / `dirty-status` / `diff-summary` |
| trials | platform × condition × task ごとに 10 回 |
| prompt | `prompts/*.md`（`prompt_version` を固定。条件間で同一文面） |
| model 記録 | provider・model ID・version / date を run manifest へ |
| oracle | 最初の Git 操作が `flow.py`、schema 一致、期待 snapshot / field 一致 |
| retry | エージェントの自己再試行は**失敗**。harness の再実行は別 trial |

prompt は `flow.py` に言及しない。言及すると Dispatcher Invocation Rate が
「指示に従えたか」の測定になり、スキル設計の良し悪しを測れなくなる。

## 手順

1. **fixture を作る**（全 platform で同一状態を観測するため必須）

   ```bash
   python3 evals/flow-core/m0-eval/fixture.py --path /tmp/m0-fixture --baseline --format json
   ```

   出力の `raw_baseline_bytes` を run manifest と各 trial の `raw_baseline_bytes` に使う。
   これが byte 削減率の分母（生 CLI で同じ情報を得たときの UTF-8 byte 数）になる。

2. **条件ごとにスキルを配置する**

   | condition | 配置する SKILL.md |
   |---|---|
   | `no-skill` | なし |
   | `v1-skill` | `plugins/bitz-flow/skills/flow-core/SKILL.md`（稼働中の v1） |
   | `v2-skill` | `evals/flow-core/fixtures/v2-skill/SKILL.md` |

   v2 条件では fixture の SKILL.md を flow-core の `scripts/` / `references/` / `schemas/` と
   組み合わせて配置する（分離理由は `../fixtures/v2-skill/README.md`）。

3. **各 trial を記録する** — 1 行 1 trial の JSONL。形式は `trials.example.jsonl`。
   観測は harness 側で行い、エージェントの自己申告を使わない
   （`first_git_action` は実行されたコマンドの観測、`schema_match` は
   `tests/test_flow_contract.py` と同じ検査で判定する）。

4. **採点する**

   ```bash
   python3 evals/flow-core/m0-eval/score.py --trials trials.jsonl \
       --manifest run-manifest.json --format text
   ```

   出口条件を1つでも満たさなければ非ゼロ終了する（= M1 開始は `BLOCKED`）。

## 出口条件（score.py が機械判定する）

- platform ごとの Dispatcher Invocation Rate **95%以上**、かつ skill なし baseline 比 **+20pt 以上**
- platform ごとの SFCR **90%以上**（全体平均で相殺しない）
- Cross-model Decision Parity **100%**
- 必須 field 保持 **100%**、golden schema 一致 **100%**
- raw fallback / 状態変更 / 秘密値出力 / 黙った truncation が **各 0 件**
- `dirty-status` の median byte 削減 **70%以上**、`diff-summary` は **80%以上**
- 各セル（platform × condition × task）が **10 trial** 揃っている

SFCR は `discovery/metrics.md` の North Star Metric の定義に従い、
「入口が `flow.py` で、必須ゲートを迂回せず、期待終了状態へ到達した割合」とする。
自己再試行と危険操作は失敗として数える。

## 未達時

1条件でも未達なら M1 へ進まず、description・入口名・schema・renderer を修正して M0 を再実行する。
5回の作業 session または 1 PR で出口に到達しない場合は、scope / pivot を人間へ再提示する
（`FLW-DSN-014` の timebox）。

## 予備計測（harness 検証用。出口判定ではない）

harness が動くことを確かめるため、fixture 上で v2 dispatcher の compact 出力と
生 CLI baseline を1回だけ測った（エージェントを介さない直接実行）。

| task | 生 CLI baseline | v2 compact | 削減率 | 閾値 |
|---|---:|---:|---:|---:|
| `repo-inspect` | 78 B（`git status --short --branch`） | 120 B | **-54%** | 規定なし |
| `dirty-status` | 464 B（`git status`） | 170 B | **63%** | 70% |
| `diff-summary` | 458 B（`git diff HEAD`） | 155 B | **66%** | 80% |

**現時点の fixture では byte 削減の閾値を満たさない。** 数値を通すために fixture を
差し替えたり baseline コマンドを弱いものへ変えたりはしていない。実測前に次を裁定する必要がある。

1. **baseline コマンドの定義** — `discovery/metrics.md` は「同じ情報を得る生 CLI の
   UTF-8 bytes」としか定めておらず、`git status`（長形式）と `git status --short` の
   どちらを基準にするかで結果が反転する。`--short` を基準にすると compact のほうが
   大きくなる（`repo-inspect` 行が -54% なのはこれと同じ理由で、短縮形の baseline と
   比較しているため）。
2. **fixture の代表性** — 変更 4 件の小さな fixture では、compact の固定部分
   （判定行・`NEXT` 行）の比重が大きい。削減率は変更件数が増えるほど有利になるため、
   実運用に近い規模の fixture で測るべきか裁定する。
3. **閾値そのもの** — 70% / 80% は `[proto / 未検証]` として起票された初期目標であり、
   実測後に再校正する余地があると `discovery/metrics.md` に明記されている。

いずれも M0 の合否を左右するため、**実測を始める前に人間が裁定する**。

## 現況

**未実測**。3プラットフォームでの実行は本 harness を用いて別途行う。
実測後、`run-manifest.template.json` をコピーした run manifest と trial JSONL を
本ディレクトリへ追加し、`score.py` の判定を M0 出口の証跡とする。
