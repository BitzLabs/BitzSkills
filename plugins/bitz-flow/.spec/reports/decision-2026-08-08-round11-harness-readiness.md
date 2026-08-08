# 裁定記録 — 第11ラウンド実測前の harness 再監査（SI-FLW-027 ほか）

- **日付**: 2026-08-08
- **裁定者**: hide（リポジトリ所有者）
- **対象**: 第11ラウンドを実測できる状態にするための harness 3 点（a/b/c）と、
  再監査で新たに見つかった `SI-FLW-027`（run manifest の予算ブロックが定数）
- **裁定の形式**: 「確認漏れが繰り返し発生している」という指摘を受け、**目視ではなく
  機械的な総当たり監査**を行ったうえでの対話裁定。hide は「問題が無ければ a/b/c とも進める」
  と述べ、監査で 4 点目が見つかったため併せて裁定した。
  記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref`）。

## 再監査の方法と結果

`ast` で 3 runner を解析し、次を総当たりで比較した（目視確認をやめた理由は、
`SI-FLW-025` と本 issue がいずれも「目視では気づけない構成の非対称」だったため）。

| 監査項目 | 結果 |
|---|---|
| CLI フラグの差分 | **`--harness-retries` が codex-cli のみ**（他は platform 固有の version フラグのみ） |
| job dict の key 差分 | `harness_retries` が codex-cli のみ |
| trial 記録の key 集合（正常路・失敗路） | **3 runner で完全一致** ✅ |
| 共通ヘルパ12種の呼び出し | **3 runner で完全一致** ✅ |
| executor が submit する関数 | 3 runner とも `run_trial` 経路 ✅ |
| run manifest の field | **`budget` ブロックが定数リテラル**（新規発見） |

**前回の説明の訂正**: 「20/10 の分割は現行 CLI では表現できないかもしれない」は誤りだった。
3 runner とも `--condition`（繰り返し可）と `--trials` を持つため、platform ごとに 2 回
走らせれば表現できる。ただし**運用者の記憶に依存する**という別の問題があり、これを (b) で扱う。

## 裁定1 — (a) `--harness-retries` を 3 runner へ揃える

**accept。** `SI-FLW-025` の裁定で `run_trial()` を common へ引き上げたが、
再試行回数は `job.get("harness_retries", 0)` から読んでおり、**この key を job へ入れているのは
`run_codex.py` だけ**だった。

| | フラグ | job へ投入 | 実際の再試行 |
|---|:-:|:-:|---:|
| codex-cli | ○ | ○ | 最大5回 |
| claude-code（旧） | **×** | **×** | **0回** |
| antigravity（旧） | **×** | **×** | **0回** |

**`SI-FLW-025` の裁定記録の記述は実態より進んでいた。** 「測定不能の検出と harness 再試行を
`run_trial()` へ一本化した」と書いたが、正しくは**検出は一本化され、再試行は claude-code /
antigravity から到達できなかった**である。ここで訂正する。

3 runner へ `--harness-retries` を足し、job へ投入する。既定値は runner で異なる。

| runner | 既定 | 根拠 |
|---|---:|---|
| codex-cli | 5 | `aggregated_output` が確率的に空になる**構造的な要因**を持つ（`SI-FLW-012` の対策強化で 2→5） |
| claude-code / antigravity | 2 | 既知の欠落要因が無いため、保守的な安全網 |

**この差は意図した差である**ことを明記する（`SI-FLW-025` の教訓は「差が事故で生まれ、
それが検出できない」ことにあり、根拠を書いた差そのものは問題ではない）。

## 裁定2 — (b) 所要 trial 数を runner が仕様から読む

**accept。** `SI-FLW-026` は「v2 は各 20 trial、baseline は各 10 trial」と定めたが、
runner の `--trials` は全 condition 一律であり、**運用者が 2 回に分けるのを忘れると
静かに旧条件で測れてしまう**。これは `SI-FLW-019` が指摘した「実装が事実上の仕様」の
裏返しであり、**仕様を実装に読ませる**べき箇所である。

- 所要数の正は採点側（`score.TRIALS_PER_CELL`。M0 出口条件の実装）に置く
- **runner がそれを import して condition ごとに解決する**。`--trials` は smoke run 用の
  一律上書きとしてのみ残し、既定値を持たせない
- `--plan` と run manifest へ `trials_per_condition` を出し、**どの母数で測った記録か**を
  事後に確かめられるようにする

これで第11ラウンドは**1 platform あたり 1 回の実行**で所要母数を満たす。

## 裁定3 — (c) v2 の trial 数を 21 とする（`SI-FLW-026` の裁定の調整）

**accept。** corpus 割当は `CORPORA[(trial - 1) % 3]` であるため、20 では偏る。

| trials/cell | small | medium | large | platform あたり v2 | 95% 上側信頼限界 |
|---:|---:|---:|---:|---:|---:|
| 20 | 7 | 7 | **6** | 60 | 4.87% |
| **21** | **7** | **7** | **7** | **63** | **4.64%** |

必要母数 59 は 20（60）でも満たすため、**これは閾値の変更ではなく割付の是正**である。
Decision Parity は (task × corpus) 単位で比較するため偏っても壊れないが、
corpus ごとの母数が揃っているほうが後の解析に耐える。

`FLW-NFR-001` を v1.2、`FLW-DSN-014` を v1.7 とし、**仕様と実装を同じ値に保つ**
（`FLW-REV-006` SYN-004 が指摘した「設計文書だけが取り残される」を繰り返さない）。

## 裁定4 — `SI-FLW-027`: run manifest の予算ブロックが定数（新規発見）

**accept。** `FLW-DSN-014` は「実績PR数・実績session数・レビュー修正回数・出口未達理由を
**run manifest へ記録**し、人間が次 budget の維持または変更を確認する」と定めており、
manifest には**そのための field が最初から存在した**。しかし 3 runner とも定数リテラルで
書いており、**全10ラウンドで一度も更新されなかった**。

```json
"budget": {
  "max_prs": 1,          // GP-001 で 3 へ再校正済み
  "max_sessions": 5,     // 同上。10 へ再校正済み
  "actual_prs": 0,       // 実績は #158 以降で 17。0 は事実でない
  "actual_sessions": 1,
  "budget_reconfirmation_ref": null   // 再確認は一度も行われていない
}
```

**これが `FLW-REV-006` GP-001「安全弁が一度も発動しなかった」ことの機械的な理由である。**
予算超過を run manifest から見る手順は、記録先が定数だったため動きようがなかった。

`SI-FLW-025` と同族である — 裁定で置いた仕組みが**到達不能な形**で実装され、
そのことが**データ構造上検出できなかった**。

- 予算値と裁定記録の参照は共有定数 `M0_BUDGET` が持ち、3 runner が読む
- 実績値は runner が知り得ないため**既定は `null`（未記入）**とする。
  **`0` のような事実でない値を書かない** — 「測ったが 0」と「未記入」が区別できなくなる
  （`SI-FLW-025` の「記録されていない／記録されたが偽」と同型）
- 予算消費の**自動集計は行わない**。runner が git 履歴を数えるのは責務違反であり、
  bitz-sdd テーマ13-E（マイルストーン予算の成果物化）の裁定を待つ

## 再発防止 — runner の構成を機械検証の対象にする

`SI-FLW-025` も `SI-FLW-027` も「目視では気づけない構成の非対称」であり、
**runner の CLI・job 構築・manifest はこれまで一度もテストされていなかった**。
`tests/test_m0_eval_runner.py`（32 件）を新設し、次を固定する。

- 3 runner の CLI が platform 固有フラグを除いて一致すること
- `--harness-retries` が全 runner にあり、既定が 1 以上であること
- runner と採点側が**同一の** `TRIALS_PER_CELL` オブジェクトを見ること
- v2 の所要数が必要母数を満たし、corpus が均等に割れること
- manifest が母数・再試行上限・再校正済み予算・裁定記録の参照を記録すること
- 実績値が未指定なら `null` であること

**負の対照で有効性を確認した**（各変異を1件ずつ入れてテストが落ちることを実測）。

| 変異 | 結果 |
|---|---|
| claude から `--harness-retries` を外す | 検出 ✅ |
| agy の再試行既定を 0 にする | 検出 ✅ |
| v2 を 20 に戻す（corpus 偏り） | 検出 ✅ |
| 予算を旧値へ戻す | 検出 ✅ |
| 実績を `0` の直書きへ戻す | 検出 ✅ |

## 裁定しなかったこと（本裁定の範囲外）

- **第11ラウンドの実測は行わない**。本裁定は実測できる状態にするところまで
- **予算消費の自動集計**は bitz-sdd テーマ13-E の裁定を待つ
- **過去ラウンドの manifest は書き換えない**（当時の記録として残す）
- **`SI-FLW-019`** の案2（proxy 乖離条件）・案3（harness 自己診断）は未裁定
- **`SI-FLW-006`**（cause 語彙）・**`SI-FLW-022`〜`024`**（新規スコープ）は未裁定

## 影響推定・ロールバック

変更は harness・回帰テスト・要件/設計文書に閉じ、**配布物と v2 fixture に影響しない**。
単独 revert できる。プラグインの version は bump しない。

実測コストは platform あたり 90 → **123 trial**（no-skill 30 + v1 30 + v2 63）。
第10ラウンドの実績（trial あたり中央値 7〜10 秒、workers=3）から、
**platform あたり 8〜10 分**、3 platform で 30 分前後と見込む。
制約は実行時間ではなく **claude のセッション上限**（第8R・第9Rで2度到達）である。

## 次アクション

1. 第11ラウンドを実測する（1 platform あたり1回の実行で所要母数を満たす）

   ```bash
   D=2026-08-08; M=evals/flow-core/m0-eval
   python3 $M/run_codex.py       --output $M/trials-codex-cli-$D-r11.jsonl   --manifest $M/run-manifest-codex-cli-$D-r11.json   --corpus-root /tmp/m0-r11-codex  --keep-logs /tmp/m0-r11-logs/codex
   python3 $M/run_claude.py      --output $M/trials-claude-code-$D-r11.jsonl --manifest $M/run-manifest-claude-code-$D-r11.json --corpus-root /tmp/m0-r11-claude --keep-logs /tmp/m0-r11-logs/claude
   python3 $M/run_antigravity.py --output $M/trials-antigravity-$D-r11.jsonl --manifest $M/run-manifest-antigravity-$D-r11.json --corpus-root /tmp/m0-r11-agy    --keep-logs /tmp/m0-r11-logs/agy
   cat $M/trials-*-$D-r11.jsonl > /tmp/combined-r11.jsonl
   python3 $M/score.py --trials /tmp/combined-r11.jsonl --manifest $M/run-manifest-$D-r11.json --format text
   ```

2. M0 出口を判定する。到達すれば3マニフェストを `0.4.0` へ bump する（`FLW-TSK-012`）
3. 未達なら残予算（検証 1 PR を本 PR で消費するため残り 0）の超過として、
   GP-001 と同じ形式で人間へ再提示する
