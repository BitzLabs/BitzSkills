# 裁定記録 — 計装の等価化と採点の再現性（SI-FLW-025 / FLW-REV-006 GP-003・GP-004・GP-005）

- **日付**: 2026-08-08
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-025`（`observation` の計装が runner 間で不均一）、および
  `FLW-REV-006` の blocking GP-003 / GP-004 / GP-005
- **裁定の形式**: `FLW-REV-006` の未消化 blocking を提示し、hide が
  「**測定系の blocking を完全消化**」を次の作業として選択した対話裁定。
  記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref`）。
- **裁定**: **accept。** `SI-FLW-025` の案1〜4 を採り、GP-003 / GP-004 / GP-005 を消化する。

## 裁定材料 — 歯止めが1つの runner でしか効いていなかった

判定ロジック（`_task_output` / `self_retried` / `_first_git_action`）は3 runner が
`run_codex.py` を `common` として共有していた。一方 **`observation` 辞書と `_one_trial` は
各 runner が個別に構築していた**ため、裁定で置いた歯止めが codex-cli にしか入っていなかった。

第10ラウンドの確定記録から（再実測なし）。

| 機構 | 導入 | codex | claude | agy |
|---|---|:-:|:-:|:-:|
| `measurable`（母数からの除外） | SI-FLW-012 | ○ | **×** | **×** |
| `harness_retries` による trial やり直し | SI-FLW-012 | ○ | **×** | **×** |
| `observation.task_output_missing` | SI-FLW-012 | ○ | **×** | **×** |
| `observation.empty_output_positions` | SI-FLW-012 | ○ | **×** | **×** |
| `observation.harness_attempts` | SI-FLW-012 | ○ | **×** | **×** |
| `observation.help_invocations` | SI-FLW-014 | ○ | **×** | **×** |

```text
trials-codex-cli-2026-08-07-r10.jsonl    measurable=True
trials-claude-code-2026-08-07-r10.jsonl  measurable=False（field 自体が無い）
trials-antigravity-2026-08-07-r10.jsonl  measurable=False（同上）
```

`score.py` は `t.get("measurable", True)` で後方互換を取るため、**claude / agy の trial は
常に「測定できた」として採点されていた**。すなわち両 platform には測定不能の概念が無かった。

### 実害

2026-08-07 の claude-code 第9ラウンドは、90 trial 中 36 trial が Claude のセッション上限
（`429 / You've hit your session limit`）で synthetic エラー応答となり **v2-skill の 30 trial が
全滅**した。エージェントの挙動ではなく上限拒否を測っているにもかかわらず、`measurable` を
持たないため**素点の FAIL として集計された**。

### `SI-FLW-020` との違い

`SI-FLW-020` は「計装の**実体**が runner ごとに違う」問題で、result code への一本化で解いた。
本件は「**歯止めの機構が runner ごとに有る／無い**」問題であり、`observation` の構築が
3箇所に散っている限り解けない。集計側は `t.get(key, default)` で吸収するため、
**「記録されていない」と「記録されたが偽」が区別できず、その事実がデータ構造上検出できない**。

## 裁定1 — GP-003: observation の共通部を `common` へ引き上げる

**accept（`SI-FLW-025` 案1・案2・案3）。**

- `build_observation()` が共通部を一括生成する。正は `REQUIRED_OBSERVATION_KEYS`。
  platform 固有 field は `platform_fields` で足す形にし、**共通部を構造的に落とせなくする**
- `failed_observation()` は runner が例外で終わった場合も共通部を必ず埋める
- 測定不能の検出と harness 再試行を `run_trial()` へ一本化し、3 runner が同じ機構を通る
- `score.py` の `instrumentation_gaps()` が**共通部の欠落を未達として列挙**する

**欠落を「エラーで停止」ではなく「未達として列挙」とした。** 旧ラウンドの記録は当然すべて
欠けるため、停止させると過去記録の再採点が一切できなくなる。どのラウンドがどの計装で
測られたかを**見えるようにする**ことが目的である。

`codex_exit_code` / `claude_exit_code` / `agy_exit_code` は `runner_exit_code` へ統一した
（由来は `exit_code_source` が持つ。`SI-FLW-020`）。

### 測定不能の検出条件（案3）は本裁定では platform 共通の枠だけを置く

claude のレート制限拒否・agy の DONE 未達を測定不能として扱う**条件そのもの**は、
`SI-FLW-019` の案3（harness 自己診断）と設計が重なるため本裁定では入れない。
枠（`measurable` / `harness_attempts` / `task_output_missing`）を3 runner へ通したことで、
条件を足す場所は1箇所になった。

## 裁定2 — GP-004: 採点規則バージョンを記録し判定を履歴として積む

**accept。** `score.py` は判定へ `scoring_rule_version`（`score.py` の内容ハッシュ先頭12桁）を
付け、`--manifest` は判定を `results` 配列へ**履歴として積む**。`result` は最新判定への
後方互換の別名として残す。同じ規則で採点し直したときは履歴を増やさず置き換える。

`manifest["result"] = report` の破壊的更新では、**どの規則で出た判定か**が失われる。
採点規則は `SI-FLW-009` / `012` / `014` / `020` / `021` / `026` で**6度**変わっており、
ラウンド間の数値比較（第8R 100% ↔ 第10R 93.3%）を議論の根拠にする以上、
比較の前提が保存されていなければならない。

## 裁定3 — GP-005: per-call の result code を保存する

**accept。** `command_result_codes`（全 command。`flow.py` 以外は `null`）を追加した。
`SI-FLW-020` で入れた `task_flow_result_codes`（task 対象のみ）と併せ、
**出力全文を保存せずに事後の再解析を厳密に行うための一次証拠**とする。

`FLW-REV-006` の再解析は `INVALID_INPUT` の同定を byte 長の近似に頼らざるを得ず、
`diff-summary`（OK 最小 220B vs `INVALID_INPUT` 63〜64B）は分離できたが
**`repo-inspect`（OK 99B vs `INVALID_INPUT` 61B）は分離できず件数を確定できなかった**。
code 列があれば同じ再解析をすべて厳密に実行できる。

## 裁定しなかったこと（本裁定の範囲外）

- **trial 記録の schema（`SI-FLW-025` 案4 / `FLW-REV-006` GP-007）は入れない。**
  GP-007 は `kind: agenda`（Gate で決める論点）であり blocking ではない。本裁定では
  `trials.example.jsonl` を現行の共通部へ追随させ、`tests/test_m0_eval_scoring.py` が
  形式例と runner の必須集合の一致を機械検証する形にとどめる。schema の範囲と時期は
  Promotion Gate で裁定する
- **`SI-FLW-019` は未裁定**。案2（proxy 乖離条件の洗い出し）・案3（harness 自己診断。
  「常に FAIL している条件」の検出を含む）は残る
- **`SI-FLW-018` は未裁定**。M0 出口を塞ぐ唯一の実質的事象。次の変更セットで扱う
- **過去ラウンドの再採点はしない。** 旧記録は `measurable` を持たないため後方互換の既定
  （測定できた）で採点され、本変更で数値は動かない。共通部の欠落は未達として現れる

## 影響推定・ロールバック

変更は harness・回帰テスト・README に閉じ、**配布物と v2 fixture に影響しない**。
単独 revert できる。プラグインの version は bump しない。

第10ラウンドを再採点すると、3 platform すべてに「observation の共通部が欠けている」が
未達として現れる（codex-cli は 4 key、claude-code / antigravity は 8 key）。
**これは退行ではなく、計装の不均一が10ラウンド見えていなかったことの可視化である。**

## 次アクション

1. `SI-FLW-018` を裁定し、claude-code の生 git 直行への対策を入れる（実装予算 1 PR）
2. 第11ラウンドを **v2 各 20 trial** で実測し、M0 出口を判定する（検証予算の残り）
3. `SI-FLW-019` の案2・案3 を裁定して恒久化する
