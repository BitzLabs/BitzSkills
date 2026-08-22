---
id: FLW-DSC-002
title: "bitz-flow v2 成功指標"
status: draft
version: 2.2
updated: 2026-08-22
owner: hide
---

# bitz-flow v2 成功指標

数値は現時点では `[proto / 未検証]` であり、実装前に fixture と計測方法を固定してから
ベースラインを取得する。モデル横断のトークン数は tokenizer に依存するため、機械ゲートは
UTF-8 byte 数と項目数を正とし、モデル別 token 数は補助指標にする。

## North Star Metric

**Scripted Flow Completion Rate (SFCR)**:

> Git / GitHub 操作を含む評価タスクのうち、エージェントが `flow.py` を入口に使い、
> 必須ゲートを迂回せず、期待する終了状態まで到達した割合。

- 初期目標: 各プラットフォームで **90%以上** `[proto / 未検証]`。総計平均で相殺しない。
- 代表タスク: status、diff、worktree作成、Issue起票、Draft PR、CI確認、squash merge、
  cleanup、release draft
- 失敗扱い: 生コマンドによる通常経路の迂回、危険操作の実行、必須再照会の欠落、
  期待終了状態との不一致

## Input Metrics

| 指標 | 定義 | 初期目標 |
|---|---|---:|
| Dispatcher Invocation Rate | Git / GitHub 操作タスクで最初に `flow.py` を実行した割合 | 95%以上 |
| Raw Fallback Rate | 理由を問わず生 `git` / `gh`へ迂回した割合 | 0% |
| Unsupported Operation Rate | 評価taskで`UNSUPPORTED`停止した割合 | M0 0%。M2 worktree通常系はLinux・macOS・Windows各0件。異常fixtureのfail-closed停止は別分母 |
| Resume Success Rate | 中断 fixture を再実行し、重複副作用なく次段階へ進めた割合 | 100% |
| Cross-model Decision Parity | 同じ fixture の判定コード・状態変更が3プラットフォームで一致する割合 | 100% |
| SDD Link Integrity | 公開した GitHub Issue と `.spec` の双方向リンクが一意に照合できる割合 | 100% |

## Token / Output Efficiency

| 操作群 | 比較対象 | 初期目標 |
|---|---|---:|
| status / branch / log / Issue / PR list | `git status`（引数なしの長形式）等、**エージェントが既定で打つ生コマンド**の UTF-8 bytes | median 40%以上削減 |
| diff summary | 生 unified diff（`git diff <base>`） | median 80%以上削減 |
| diff detail | `--unified=3` の対象 hunk | median 40%以上削減 |
| 書込み結果 | 生 commit / push / gh 出力 | median 80%以上削減 |

圧縮率だけを最適化しない。各 fixture について「次の安全な行動を決める必須フィールド」を定義し、
その保持率を **100%** とする。情報が上限を超えた場合は黙って切り捨てず、
`truncated: true`、総件数、次の絞込み条件を返す。

### 測定条件（2026-08-05 裁定。`SI-FLW-009` / `FLW-NFR-008`）

閾値だけを定めても、baseline の選び方で合否が反転する。次を固定する
（裁定記録 `.spec/reports/decision-2026-08-05-si-flw-009-byte-denominator.md`）。

1. **baseline は task ごとの固定コマンドとする。** `status` 系は
   `git status`（引数なしの長形式）、`diff summary` は生 unified diff（`git diff <base>`）。
   分母は fixture から測り、trial 時のエージェントの挙動に依存させない。
2. **parse 入力を分母にしない。** `--porcelain` 系は `flow.py` 自身が parse に使う形式であり、
   分母にすると公正さを欠く。
3. **truncation で削減率を稼がない。** byte 比較は `truncated: false`（全件表示）の trial
   だけで行い、省略された出力を全量 baseline と比較しない。
4. **corpus は規模の異なる3 fixture**（小 / 中 / 大）とし、trial ごとに自分の corpus の
   baseline と比べた削減率を出して median を取る（median 同士を割ると規模が混ざる）。
   corpus は決定論的に構築できる形で version 管理する（`evals/flow-core/m0-eval/fixture.py`）。

`status` の閾値は 70% → **40%** へ再校正した。compact は `--porcelain=v1` と同型式
（1項目1行）で header 行のぶん必ず太るため、公正な分母では 70% は原理的に達成できない。
実測は median 47.5%（3 platform で 44.8〜47.6%）。`diff summary` の 80% は据え置き。

### 旧測定条件（2026-07-31 裁定。`SI-FLW-007`。破棄）

`status` 系の分母を「`no-skill` 条件でエージェントが実際に消費した出力」とする案A を採っていたが、
選ぶ形式（porcelain / 長形式）と叩いた回数が platform ごとに違うため、**同一 renderer が
5.9%〜75.0% に振れた**。`SI-FLW-009` の裁定で破棄した。

## Guardrail Metrics

| 指標 | 許容値 |
|---|---:|
| 誤った破壊的状態変更 | 0件 |
| stale head / stale snapshot を使った commit・merge・cleanup | 0件 |
| process環境値・認証出力・raw stderr の構造化出力混入 | 0件 |
| dry-run での外部状態変更 | 0件 |
| CI failure / pending を green と誤判定 | 0件 |
| `.spec` の人間専用 status を GitHub 側から自動変更 | 0件 |

## Performance

- 読み取り専用のローカル Git 操作: fixture の p95 で **500ms以内** `[proto / 未検証]`
- dispatcher 自身の上乗せ: 生コマンド実行時間を除き p95 **100ms以内** `[proto / 未検証]`
- GitHub 操作: ネットワーク時間を除外した parse / normalize 処理 p95 **100ms以内**
- すべての外部コマンドに 1〜300秒の明示 timeout を適用し、timeout は安全側停止にする。

benchmarkは保存fixtureを使い、warm-up 5回後に最低30回計測する。計測区間はprocess runner呼出前後と
parse/normalize単体を分け、OS、Python、Git、gh、filesystem、fixture件数・bytesをmanifestへ記録する。
CIでは同一基準環境の直近baselineに対する20%超の回帰をFAILとする。

## 計測設計

1. `tests/fixtures/bitz_flow/` にraw baseline command、入力、生出力、期待圧縮出力、
   operation別必須field、truncation合否を保存する。
2. unit test で終了コード・JSON Schema・副作用・median/p90/absolute bytesを測る。
3. `evals/flow-core/` でskillなし、v1、v2を同一promptで比較する。
4. platform×taskごとに10trial実施し、provider/model/version/date、prompt version、成功oracle、
   retry有無をrun manifestへ記録する。
5. agent自身のretryは最初のtrial失敗として数え、harness再実行は別trialにする。
6. 各platformでSFCR 90%以上を要求し、全体平均で相殺しない。
7. 実測値が揃うまで外部事例の削減率を本製品の達成値として主張しない。

M0のtask、trial、baseline、出口条件の完全な正はFLW-DSN-014とする。
