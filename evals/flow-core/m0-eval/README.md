# M0 eval — 3プラットフォーム実測 harness

`FLW-DSN-014` の M0 eval protocol を実行するための道具一式と、実測結果。
**第2ラウンド（`*-r2`）が有効な最新の測定**で、第1ラウンドは harness 欠陥により
出口判定の証跡にならない（下記「現況」）。

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

1. **corpus を作る**（全 platform で同一状態を観測するため必須）

   ```bash
   python3 evals/flow-core/m0-eval/fixture.py --path /tmp/m0-corpus --size all --baseline --format json
   ```

   出力の `raw_baseline_bytes` は **`diff-summary` の分母**として各 trial へ記録する。
   `dirty-status` の分母は `no-skill` 条件の実測値なので、ここでは測らない。

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
   `truncated` は result の同名 field をそのまま記録する。byte 比較の対象になるため、
   全件を見せる設定（`--limit` を件数以上）で測ること。

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
- `dirty-status` の median byte 削減 **70%以上**（分母 = `no-skill` の実測 median）、
  `diff-summary` は **80%以上**（分母 = 生 unified diff）。いずれも `truncated: false` の trial のみ
- 各セル（platform × condition × task）が **10 trial** 揃っている

SFCR は `discovery/metrics.md` の North Star Metric の定義に従い、
「入口が `flow.py` で、必須ゲートを迂回せず、期待終了状態へ到達した割合」とする。
自己再試行と危険操作は失敗として数える。

## 未達時

1条件でも未達なら M1 へ進まず、description・入口名・schema・renderer を修正して M0 を再実行する。
5回の作業 session または 1 PR で出口に到達しない場合は、scope / pivot を人間へ再提示する
（`FLW-DSN-014` の timebox）。

## 測定条件（2026-07-31 裁定。`SI-FLW-007`）

閾値だけを定めても baseline の選び方で合否が反転することを実測で確認したため、次を固定した
（裁定記録: `plugins/bitz-flow/.spec/reports/decision-2026-07-31-byte-baseline-measurement.md`）。

1. **`dirty-status` の baseline は固定コマンドにしない。** `no-skill` 条件でエージェントが
   実際に消費した出力の byte 数を分母とし、platform ごとに median を取る。
2. **`diff-summary` の baseline は生 unified diff**（`git diff <base>`）。`fixture.py` が測る。
3. **byte 比較は `truncated: false` の trial だけ**で行う。省略した出力を全量 baseline と
   比較しない（`score.py` が truncated を除外し、全件 trial が無ければ未達として扱う）。
4. **corpus は規模の異なる3 fixture**（小 4 / 中 30 / 大 120 モジュール相当）。median は横断で取る。

### 裁定の根拠になった実測（2026-07-31）

| baseline 候補 | 小(7 件) | 中(33 件) | 大(123 件) |
|---|---:|---:|---:|
| `git status`（長形式） | 59.6% | 47.0% | 40.2% |
| `git status --short --branch` | -71.9% | -16.5% | -4.4% |
| `git status --porcelain=v2 --branch` | 74.2% | 84.2% | 85.8% |
| `git diff HEAD`（生 unified diff） | 81.7% | 89.0% | 90.0% |
| `git diff --stat HEAD` | 17.6% | 31.6% | 33.8% |

- diff は生 unified diff 比なら全規模で 80% を超える。
- status は `git status`（長形式）では達成できず、**規模が大きいほど悪化する**。
- `--porcelain=v2` なら 85% 出るが、これは `flow.py` 自身が parse に使う形式であり、
  自分の入力を分母にするのは公正さを欠くため採らなかった。
- 大 fixture では既定 limit 50 のとき `git status` 比が 40.2% → 71.7% へ跳ねる。
  123 件中 50 件しか出していないため**同じ情報ではない**。これが条件3 の理由である。

閾値（70% / 80%）は本裁定では変更していない。案A の実測後に、必要なら `FLW-NFR-002` の
supersede として別途裁定する。

## 現況

**第2ラウンド（3 platform 270 trial）実測済み・出口 FAIL**（2026-08-03）。
設計修正により **claude-code / codex-cli は全閾値を満たした**が、**antigravity が未達**である。
`--sandbox=false` の修正により第1ラウンドの全滅（`first_git_action=none` 90件）は解消し、
agy でも初めて有効な測定が取れた。

### 第2ラウンド結果（`*-r2` ファイル。各 platform 90 trial）

| 指標 | 閾値 | claude-code | codex-cli | antigravity |
|---|---|---|---|---|
| Dispatcher Invocation Rate | 95%以上 | **100%** ✅ | **100%** ✅ | **83.3%** ❌ |
| baseline 比改善 | +20pt 以上 | +100pt ✅ | +100pt ✅ | +83.3pt ✅ |
| SFCR | 90%以上 | **100%** ✅ | **100%** ✅ | **80.0%** ❌ |
| 必須 field 保持 | 100% | **100%** ✅ | **100%** ✅ | **83.3%** ❌ |
| golden schema 一致 | 100% | 100% ✅ | 100% ✅ | 100% ✅ |
| raw fallback | 0件 | **0件** ✅ | **0件** ✅ | **5件** ❌ |
| 状態変更 | 0件 | **0件** ✅ | **0件** ✅ | **2件**（実質1件）❌ |
| `diff-summary` byte 削減 | 80%以上 | **89.0%** ✅ | **89.0%** ✅ | **88.5%** ✅ |
| `dirty-status` byte 削減 | 70%以上 | **5.9%** ❌ | **75.0%** ✅ | **25.1%** ❌ |

第1ラウンド比では claude の SFCR 67%→100%・field 44%→100%・`diff-summary` 62%→89.0%、
codex の SFCR 63%→100%・field 67%→100% と、`--base` 既定の HEAD 化と compact 誘導の是正が効いた。
codex で `v2-skill/repo-inspect` の 9/10 が output 0 byte になった事象も解消（10/10 が 120 byte）。
Decision Parity の「揺れ」は score.py の既知の制約（corpus を grouping key に含めない）であり、
実データ側の不一致ではない。

### antigravity だけが Mandatory entry protocol を守り切れない

v2 条件 30 trial のうち **5 件が生 git で開始**した（claude / codex は 0 件）。
raw log で確認した最悪例（`v2-skill/diff-summary#6`）は、生 git を4回叩いたうえで
`git show --stat --summary HEAD > stats.txt` とファイル書き込みまで行っている。
SKILL.md は同一で、差が出たのは platform 側の傾向である。
「文章を長くするのではなく description・入口名・命名・next action を直す」（`FLW-DSN-010`）に
沿った次の一手が要る論点で、`FLW-NFR-001` の platform 別 90% 要件に直接効く。

state_change 2件のうち **1件は harness の誤検知**である（下記）。実質1件。

### 第2ラウンドで判明した harness 欠陥（corpus の trial 間共有）

harness は condition × corpus サイズごとに repo を**1つだけ**作り、その corpus を使う
全 trial で共有する。しかも `--workers 3` で並列実行する。このため、ある trial が repo を
変更すると同一 corpus の別 trial の `before` / `after` 比較へ混入し、**無実の trial が
`state_change` として記録される**。

第2ラウンドの `antigravity/v2-skill/diff-summary#9` が該当する。この trial は flow.py しか
実行していない（raw log で6コマンドすべてを確認済み）にもかかわらず `state_change=true` と
なった。原因は同じ large corpus を使う `#6` が並行実行中に `stats.txt` を作ったことで、
実際に corpus へ `?? stats.txt` が残っている。

したがって **antigravity の state_change は 2件ではなく実質1件**（`#6` のみが真の違反）。
切り分けるには corpus を trial ごとに分離するか、書き込みを伴う trial を直列化する必要がある。
現状は raw log と突き合わせないと真偽を判定できない。

### `dirty-status` の byte 削減は分母がエージェントの気まぐれに左右される

`SI-FLW-007` は分母を「`no-skill` でエージェントが実際に消費した出力 byte」と定めた。
raw log で確認した no-skill の実際の振る舞いは platform でまるで違う。

| platform | no-skill が実行したコマンド | 削減 |
|---|---|---:|
| claude-code | `git status --porcelain=v1`（**1回**） | 5.9% |
| codex-cli | `git status --short` + `git status --branch --porcelain=v2`（**2回**） | 75.0% |
| antigravity | `git status`（**長形式**）中心。`git status -s` も混在 | 25.1% |

corpus 別に見るとばらつきはさらに大きい。

| corpus | claude no-skill | codex no-skill | v2 compact | claude 削減 | codex 削減 |
|---|---:|---:|---:|---:|---:|
| small | 542 | 248 | 229 | 67.2% | 7.3% |
| medium | 563 | 4706 | 666 | **-18.3%** | 85.8% |
| large | 3688 | 4220 | 2217 | 39.9% | 47.4% |

**同一の compact renderer が、分母の取り方だけで 5.9%〜75.0% に振れる。**
claude は porcelain（compact と同じ1項目1行の機械可読形式）を1回だけ叩くので分母が小さく、
codex は同じ情報を2回取得するので分母が膨らむ。harness は no-skill の raw コマンド出力を
連結して分母にするため、**冗長に叩いた platform ほど削減率が高く出る**。

つまりこの指標が現在測っているのは renderer の性能ではなく、
「no-skill のエージェントがたまたま何回・どの形式で叩いたか」である。
`FLW-NFR-002` の 70% が妥当かどうか以前に、`SI-FLW-007` が定めた分母の定義に
再検討の余地がある（例: platform ごとに評価する／重複取得を正規化する／
`dirty-status` の価値を byte ではなく field 保持・gate 遵守・一貫性で測る）。

閾値と測定条件の変更はいずれも要件の変更であり、エージェントが決めてよい事項ではない。
spec-issue として起票し、人間の裁定を仰ぐ。

### 第1ラウンド（harness 欠陥により証跡にならない）

3 platform × 3条件 × 3 task × 10 trial = 270 trial を実行し、
`trials-<platform>-2026-08-03.jsonl` と platform ごとの部分 run manifest を本ディレクトリへ
記録した（`-r2` の付かないファイル）。ただし**この結果は M0 出口判定の証跡として使えない**。
未達の大半が harness 側の欠陥に由来し、スキル設計の良し悪しを測れていないためである。

### 第1ラウンドで判明した harness 欠陥

| 欠陥 | 影響 | 対処 |
|---|---|---|
| `agy --sandbox` を bare flag で渡していた。`--sandbox=<true\|false>` の bool で既定 true のため sandbox が解除されず、ターミナル隔離で `run_command` が実行できない | antigravity 90 trial 全件が `first_git_action=none` / `command_events=0`（`ask_permission` へ落ちる）＝**全滅** | `--sandbox=false` を明示（`run_antigravity.py`）。**実機未検証** — 検証時に Gemini のクォータ上限に当たったため、再実測時に最初の数 trial で `command_events>0` を確認すること |
| raw event log を保存していなかった | codex `v2-skill/repo-inspect` の 9/10 で「`flow.py` が exit 0 なのに出力 0 byte」を観測したが、harness の欠陥か platform の挙動かを**事後に切り分けられない** | 全 harness へ `--keep-logs DIR` を追加。再実測は必ず指定する |

再実測後、`score.py` の判定を M0 出口の証跡とする。

### 第1ラウンドで判明した設計側の論点（harness 欠陥ではない）

いずれも `FLW-DSN-010` の「文章を長くするのではなく description・入口名・command 命名・
result の next action を直す」に沿って修正済み。効果の確認は再実測で行う。

- **`diff-summary` で `--base` が指定されない**（claude-code の v2 10/10 が該当）。既定が
  `base=index` で rename を検出せず、「リネームがあるか」を問う prompt に答えられていなかった。
  prompt は「直前のコミットからの変更量」なので `--base HEAD` が正解であり、**正当な失敗**。
  → `--base` の既定を `HEAD` へ変更し（生 git の慣習ではなくエージェントの意図側へ寄せる）、
  `git status` の `NEXT git.diff-summary` にも `base=HEAD` を明示した。index 比較は
  `--base index` で引き続き可能。`tests/test_flow_contract.py` が既定・退避路・NEXT を固定する。
- **byte 削減率未達の主因は `--format json` への誘導**。v2 `SKILL.md` の
  「機械処理には `--format json` を使う」により、エージェントが自分を「機械処理」と解釈して
  JSON を選ぶ。同一 corpus で compact 120 byte に対し JSON 1920 byte（**約16倍**）であり、
  `dirty-status` 41% / `diff-summary` 62% の未達に直結していた。
  → 「compact のまま読む。`--format json` は別のプログラムへ渡すときだけ」へ改めた。
  byte の分母・分子は `SI-FLW-007` の裁定により**エージェントが実際に消費した出力**なので、
  JSON を選ぶこと自体が正当に減点される。閾値（70% / 80%）は変更しない。
