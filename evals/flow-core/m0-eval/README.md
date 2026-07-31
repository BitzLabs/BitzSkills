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

**未実測**。測定条件は 2026-07-31 の裁定で確定済み。3プラットフォームでの実行は
本 harness を用いて別途行う。
実測後、`run-manifest.template.json` をコピーした run manifest と trial JSONL を
本ディレクトリへ追加し、`score.py` の判定を M0 出口の証跡とする。
