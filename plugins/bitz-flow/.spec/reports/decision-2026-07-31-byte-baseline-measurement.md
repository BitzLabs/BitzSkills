# 裁定記録 — byte 削減率の測定条件（SI-FLW-007）

- **日付**: 2026-07-31
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-007`（`FLW-NFR-002` が前提とする fixture corpus と raw baseline command の未定義）
- **裁定の形式**: 実測比較表を提示したうえでの対話裁定。エージェントは裁定結果を成果物へ反映する。

## 裁定材料（実測、2026-07-31）

規模の異なる3 fixture で、baseline 候補ごとの削減率を実測した。

### fixture

| 規模 | 変更件数 | compact status（全件） | compact status（既定 limit 50） | compact diff（全件） | compact diff（既定 50） |
|---|---:|---:|---:|---:|---:|
| 小 | 7 | 220 B | 220 B | 220 B | 220 B |
| 中 | 33 | 657 B | 657 B | 789 B | 789 B |
| 大 | 123 | 2208 B | 1045 B | 2792 B | 1292 B |

### `git.status` の baseline 候補（閾値 70%）

| baseline | 小(7) | 中(33) | 大(123) | 判定 |
|---|---:|---:|---:|:--:|
| `git status`（長形式） | 59.6% | 47.0% | 40.2% | ❌ |
| `git status --short --branch` | -71.9% | -16.5% | -4.4% | ❌ |
| `git status --porcelain=v2 --branch` | 74.2% | 84.2% | 85.8% | ✅ |

### `git.diff-summary` の baseline 候補（閾値 80%）

| baseline | 小 | 中 | 大 | 判定 |
|---|---:|---:|---:|:--:|
| `git diff HEAD`（生 unified diff） | 81.7% | 89.0% | 90.0% | ✅ |
| `git diff --stat HEAD` | 17.6% | 31.6% | 33.8% | ❌ |
| `git diff --numstat HEAD` | -101.8% | -38.2% | -26.3% | ❌ |
| `git diff --name-status HEAD` | -126.8% | -55.6% | -41.9% | ❌ |

### 読み取り

1. diff は `metrics.md` が既に明記する「生 unified diff」比で全規模 80% を超える。
2. status は最も自然な `git status`（長形式）では達成できず、しかも**規模が大きいほど悪化する**
   （59.6% → 40.2%）。長形式の per-file 行が既に短く、compact との差が小さいため。
3. `--porcelain=v2` を baseline にすれば 85% 出るが、これは `flow.py` 自身が parse に使う形式であり、
   自分の入力を分母にするのは公正さを欠く。
4. truncation が数値を大きく動かす。大 fixture では既定 limit 50 のとき `git status` 比が
   40.2% → 71.7% へ跳ねるが、123 件中 50 件しか出しておらず**同じ情報ではない**。

## 裁定

**案A を採用する — baseline は no-skill 条件の実測値とする。**

1. **status 系の baseline は固定コマンドにせず、eval の `no-skill` 条件で
   エージェントが実際に消費した出力の UTF-8 byte 数**を分母にする。
   platform ごとに median を取る。恣意的な比較対象の選択を排除するため。
2. **`diff-summary` の baseline は生 unified diff（`git diff <base>`）**で確定する。
   `metrics.md` の記述どおりであり、全規模で閾値を満たすことを実測済み。
3. **truncation で削減率を稼がない。** byte 比較は `truncated: false`（全件表示）の trial
   だけで行う。省略された出力を全量 baseline と比較しない。
4. **corpus は規模の異なる3 fixture**（小 7 件 / 中 33 件 / 大 123 件相当）とし、
   median はその横断で取る。corpus は決定論的に構築できる形で version 管理する。
5. 閾値（70% / 80%）は**現時点では変更しない**。案A の実測値が出た後に、必要なら
   `FLW-NFR-002` の supersede として別途裁定する（提案3 は保留）。
6. 削減率を緩める裁定を将来行う場合でも、必須 field 保持 100% と blocking 項目保持 100% は
   緩めない（`FLW-NFR-002` の他の受入基準）。

## 根拠

- 案B（`git status` 長形式に固定して閾値を下げる）は正直だが、`FLW-NFR-002` が implementing で
  EARS 節を書き換えられないため supersede が必要になり、実測前に閾値を動かすことになる。
- 案C（`--porcelain=v2` を baseline）は数値を通せるが、「通るように測った」という疑いが残る。
- 案A は eval の `no-skill` 条件が既に存在するため追加コストが小さく、
  「skill が無いときエージェントが実際に何を消費するか」という**本来測りたい量**に一致する。
  分母が platform / model により変動する点は median と trial 数（10）で吸収する。

## 反映先

| 反映先 | 内容 |
|---|---|
| `.spec/discovery/metrics.md` | Token / Output Efficiency の測定条件を明記（version 2.1） |
| `.spec/design/FLW-DSN-014.md` | M0 出口条件の byte 行へ測定条件を追記（version 1.4） |
| `.spec/spec-issues/SI-FLW-007.md` | 実測データと裁定を追記し accepted へ |
| `evals/flow-core/m0-eval/fixture.py` | corpus 3規模の構築 |
| `evals/flow-core/m0-eval/score.py` | baseline を no-skill trial から算出、truncated trial を byte 計測から除外 |
| `evals/flow-core/m0-eval/README.md` | 予備計測節を裁定後の測定条件へ更新 |

## 保留

`SI-FLW-007` 提案3（閾値そのものの再校正）は保留。案A での実測後に、`FLW-NFR-002` の
supersede が必要かを改めて裁定する。
