# 裁定記録 — 第7ラウンドで判明した3件（SI-FLW-014 / SI-FLW-012 再検討 / SI-FLW-015）

- **日付**: 2026-08-06
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-014`、`SI-FLW-012` の対策見直し、`SI-FLW-015`
- **裁定の形式**: M0 第7ラウンド（3 platform 同一 fixture）の実測を提示したうえでの対話裁定。
  記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref` でエージェントが status 遷移を実行）。

## 共通の前提（第7ラウンドの到達点）

`SI-FLW-013` 適用後、閾値項目は claude-code / codex-cli が全項目クリア、antigravity も
byte 削減が回復した（`dirty-status` 37.0% → 46.4%）。残る未達は 2 点のみである。

| platform | 未達 |
|---|---|
| codex-cli | `repo-inspect` の母数 7/12 |
| antigravity | 必須 field 保持 93.3%（2 trial） |

## 裁定1 — `SI-FLW-014`（`--help` を採点対象から外す）

### 材料

`flow.py git status --help` が `TASK_FLOW_PATTERN`（`flow\.py.*git\s+status`）に一致し、
`_task_output` が最後の該当実行を採るため argparse の usage が採点値になる。usage には
`code` も `operation` も `snapshot` も無いため必須 field の検査は必ず落ちる。

第7ラウンドで `--help` を実行したのは antigravity だけである（claude 0/30・codex 0/30）。
該当 trial ではエージェントが正しい実行（218 B）を済ませたうえでヘルプを見ていた。

### 裁定

**accept。`_task_output` が match を集める際に `--help` / `-h` を含む実行を落とす。**

- `TASK_FLOW_PATTERN` 自体は変えない（否定先読みでパターンを複雑にするより選択規則で落とす）
- 除外した実行は `observation.help_invocations` へ残す（黙って捨てない）
- **`--help` しか実行しなかった trial は従来どおり失敗**（除外が「なかったこと」にならない）
- **`--base HEAD~1` のような比較元の誤りは引き続き失敗として数える**
  （除外規則がエージェントの誤りを覆い隠さない）
- `first_git_action` の判定は変えない。`--help` であっても「生 git ではなく `flow.py` を
  選んだ」ことは事実であり、入口遵守の観点では成功として数えてよい

### 根拠

`--help` は operation の実行ではなく result envelope を返さない。これを task の出力として
扱うのは**測定系の取り違え**であり、`SI-FLW-012`（出力欠落を失敗と誤読していた件）と同種である。

## 裁定2 — `SI-FLW-012` の対策見直し（位置依存に再試行は効かない）

### 材料

第7ラウンド（`--trials 12`）の task 別内訳。

| task | trial | 測定不能 | `harness_attempts` 分布 |
|---|---:|---:|---|
| `repo-inspect` | 12 | **5** | 1:3 / 2:2 / **3:7** |
| `dirty-status` | 12 | 0 | 1:12 |
| `diff-summary` | 12 | 0 | 1:12 |

出力欠落は必ずセッション内2番目のコマンドで起きる。`repo-inspect` は task 対象の呼び出しが
その位置に来るため、**再試行しても毎回同じ脆弱な位置に戻る**。12 trial 中 7 trial が3回とも
失敗した（1回あたりの失敗率が約7割なら3回でも 0.7³ ≒ 34% が残る）。

**位置依存の欠陥に対して位置を変えない対策であった**というのが `SI-FLW-012` 裁定時の見落としである。

### 裁定

**再試行回数の増加と trial 数の増加を併用する。**

- `--harness-retries` の既定を 2 → **5** へ引き上げる
- `repo-inspect` の測定可能 10 件を確保するため `--trials` を **16** 程度へ増やす
- `FLW-DSN-014` は「harness再実行は別trial」と既に規定しており、**trial 数を増やすこと自体は
  仕様変更にあたらない**。`FLW-NFR-001` の「各10 trial」は下限であって上限ではない

### 根拠

根治（codex 側の初回実行の不安定性そのものへの対処）は原因が手の届かない場所にあり、
時間が読めない。回数と件数の併用は確実性が高く、既存規定の範囲で実施できる。

### 裁定しなかったこと

- `FLW-NFR-001` / `FLW-DSN-014` の条文は変更しない。閾値も trial 数の規定も現行のままとする。
- codex-cli 上流への不具合報告は本裁定では扱わない。

## 裁定3 — `SI-FLW-015`（`cursor` を出力から落とす）

### 材料

`TRUNCATED shown=50 total=122 cursor=sha256:1ec4#50` と提示するが `--cursor` 引数は存在しない。
第7ラウンドの claude-code `diff-summary#6` は提示された値を渡して `INVALID_INPUT`（exit 2）を
受け、`--cursor` を外して再実行した（`self_retried` として減点。SFCR は 96.7% で閾値内）。

`SI-FLW-011`（`NEXT` が提示した snapshot を dispatcher 自身が拒否する）と同じく、
**出力が入力契約と噛み合っていない**。

### 裁定

**accept。案2（`cursor` を出力から落とす）を採用する。**

- `paginate()` の戻り値から `cursor` を外す。compact の `TRUNCATED` 行も `shown` / `total` のみ
- `result-v1.schema.json` の `page` から `cursor` を削除し、truncated 時の必須 key を
  `shown` / `total` にする
- `references/output-contract.md` と v2 fixture SKILL.md の記述を実態へ揃える
- 残りが要るときの回復経路は **`--limit` を大きくして取り直す**。これを契約として明文化する

### 根拠

- 継続位置は `--limit` の指定で足り、打ち切りの可視化は `shown` / `total` が担う
  （`silent_truncation` は 3 platform とも 0 件であり、この性質を失わない）
- **受け取れない値を見せない**という点で `SI-FLW-011` / `SI-FLW-013` と一貫する
- M0 の scope に収まる。案1（`--cursor` を受け付ける）は機能追加であり、M1 以降で
  ページング要求が実際に生じたときに改めて検討すればよい

### 裁定しなかったこと

- `--cursor` の受け付け（案1）は**採らない**。M0 の scope 拡大にあたる。
- `snapshot` 自体の扱いは変更しない（`--snapshot` による楽観ロックは維持する）。

## 次アクション

1. `run_codex.py` へ `--help` 除外と `--harness-retries` 既定 5 を実装する
2. `result.py` / schema / 契約文書 / v2 SKILL.md から `cursor` を落とす
3. `tests/test_flow_contract.py` を更新する（`cursor` 不在の検査と `--limit` による回復経路の固定）
4. 3 platform を再実測する。codex-cli は `--trials 16` で測定可能 10 件を確保する
5. 既存要件の条文は変更しない（`FLW-NFR-001` / `FLW-NFR-008` / `FLW-DSN-014`）

## 備考

`SI-FLW-011` / `SI-FLW-013` / `SI-FLW-015` は同じ性質の欠陥である。
**dispatcher が「受け取れない値」「使わせたくない選択肢」を出力に見せていた**ことが
共通の原因であり、いずれも「見せない」方向で裁定した。M0 eval はこの種の契約の穴を
3 platform の挙動差として顕在化させた。
