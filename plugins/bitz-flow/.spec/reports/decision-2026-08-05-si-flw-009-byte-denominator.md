# 裁定記録 — dirty-status の byte 削減の分母定義（SI-FLW-009）

- **日付**: 2026-08-05
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-009`（`dirty-status` の byte 削減の分母が `no-skill` エージェントのコマンド選択に
  左右され、同一 renderer が platform 間で 5.9%〜75.0% に振れる）
- **裁定の形式**: 分母候補の再実測を提示したうえでの対話裁定。
  記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref` でエージェントが status 遷移を実行）。
- **前提**: 本裁定は `SI-FLW-007`（2026-07-31 裁定、案A）の follow-up であり、案A を置き換える。

## 裁定材料

### 案A の実測結果（第2ラウンド、3 platform）

| platform | `no-skill` が実際に叩いたコマンド（raw log で確認） | 削減 | 判定 |
|---|---|---:|:--:|
| claude-code | `git status --porcelain=v1`（1回） | 5.9% | ❌ |
| codex-cli | `git status --short` + `git status --branch --porcelain=v2`（2回） | 75.0% | ✅ |
| antigravity | `git status`（長形式）中心 | 25.1% | ❌ |

同一の compact renderer が、分母の取り方だけで 5.9%〜75.0% に振れた。原因は
(1) エージェントが選ぶ形式が platform ごとに違う、(2) harness が raw 出力を連結して分母にするため
**冗長に叩いた platform ほど有利**になる、の2つ。

### 分母候補の再実測（2026-08-05。fixture 3規模、`truncated: false` の全件表示で比較）

| corpus | compact（全件） | `git status` 長形式 | `git status -s` / `--porcelain=v1` | `--branch --porcelain=v2` |
|---|---:|---:|---:|---:|
| small | 230 | 575 | 120 | 854 |
| medium | 667 | 1271 | 556 | 4150 |
| large | 2218 | 3721 | 2106 | 15600 |

削減率:

| corpus | vs 長形式 | vs `--porcelain=v1` | vs `--porcelain=v2` |
|---|---:|---:|---:|
| small | 60.0% | **-91.7%** | 73.1% |
| medium | 47.5% | **-20.0%** | 83.9% |
| large | 40.4% | **-5.3%** | 93.2% |

## 読み取り

1. **compact は `--porcelain=v1` より常に大きい**。両者とも1項目1行の同型式であり、compact は
   header 行（`OK git.status snapshot=… branch=main changed=8`）が付くぶん必ず太る。
   byte 削減は `dirty-status` では原理的に大きくならない。
2. **閾値 70% を満たせる分母は `--porcelain=v2` だけ**であり、それは `flow.py` 自身が parse に
   使う入力形式である（`SI-FLW-007` が「公正さを欠く」として除外した当のもの）。
   すなわち **70% はどの公正な分母を選んでも達成不能**である。
3. `SI-FLW-007` の裁定は、長形式が 70% に届かないことを理由に案A を選んでいた。これは
   **閾値を所与として分母を選んだ**ことになり、順序が逆である
   （本 issue のガードレール「数値を通すために分母を大きい方へ選び直さない」に抵触する）。
4. `diff-summary` は分母が固定（生 unified diff）のため3 platform とも 88.5〜89.0% で安定し、
   閾値 80% を満たす。問題は `dirty-status` に限る。

## 裁定

**accept。案3（固定 baseline へ戻す）と案4（`dirty-status` の byte 閾値の再校正）を組み合わせる。**
`FLW-NFR-002` を supersede し、後継要件で次を固定する。

1. **`git.status` の分母を固定する** — `git status`（引数なしの長形式）。エージェントが
   何も知らないときに既定で打つコマンドであり、実際 antigravity の `no-skill` はこれを選んでいた。
   parse 入力である `--porcelain` 系は分母にしない。
2. **分子は全件表示（`truncated: false`）の compact とする**。truncation で削減率を稼がない
   （`metrics.md` の既存規定を要件へ格上げする）。
3. **`git.status` の閾値を median 70% → 40% へ再校正する**（実測 median 47.5%、最小 40.4%）。
   公正な分母を先に固定し、そのうえで実測から閾値を引く。
4. **`git.diff-summary` は現状維持**（固定分母 = 生 unified diff、median 80%以上）。
5. **必須 field 保持 100% と blocking 項目保持 100% は緩めない**（`SI-FLW-007` の裁定6 を維持）。
   削減率の緩和と情報欠落の取引は行わない。

### 裁定の根拠

- 閾値 40% は「甘くした」のではなく、**公正な分母を固定した結果として実測から引いた値**である。
  数値ありきで分母を選んだ案A の誤りを繰り返さない。
- byte 閾値を完全に外す案（案4 単独）は、renderer が将来太っても検知できなくなるため採らない。
  下限を残す。
- `dirty-status` の価値の主軸（必須 field 保持・blocking 項目保持・gate 遵守・cross-model の
  判断一致）は後継要件と `FLW-NFR-001` が引き続き測る。

### 裁定しなかったこと（本裁定の範囲外）

- 案1（重複取得の正規化）と案2（platform 別判定）は、分母を固定した時点で論点が消えるため
  個別には採らない。
- `FLW-NFR-001` の platform 別判定の規定は変更しない。

## 次アクション

1. `FLW-NFR-002` を supersede する後継要件を起票し、旧要件を deprecated にする。
2. 後継 ID を参照する成果物（design の `implements`、タスクの `implements`、
   `tests/fixtures/flow/byte-manifest.json` と `tests/test_flow_contract.py` の参照）を更新する。
3. `.spec/discovery/metrics.md` の Token / Output Efficiency 節を新しい測定条件へ更新する。
4. `score.py` の分母算出を固定 baseline へ変更する。
5. **既存 270 trial を再採点して**、platform 間のばらつきが縮むことを確認する（再実測は不要）。
