---
id: SI-FLW-009
raised_by: M0 eval 第2ラウンド実測（FLW-TSK-012、2026-08-03）
target: dirty-status の byte 削減の分母が no-skill エージェントのコマンド選択に左右され、同一 renderer が platform 間で 5.9%〜75.0% に振れる
proposed_change_type: modify
status: accepted
---
- **目的**: `SI-FLW-007` の裁定（案A）は `dirty-status` の分母を
  「`no-skill` 条件でエージェントが実際に消費した出力の byte 数」と定めた。
  第2ラウンドでこの測定法を3 platform で実行した結果、**同一の compact renderer が
  分母の取り方だけで 5.9%〜75.0% に振れる**ことが判明した。

  | platform | no-skill が実際に実行したコマンド（raw log で確認） | 削減 | 判定 |
  |---|---|---:|:--:|
  | claude-code | `git status --porcelain=v1`（**1回**） | 5.9% | ❌ |
  | codex-cli | `git status --short` + `git status --branch --porcelain=v2`（**2回**） | 75.0% | ✅ |
  | antigravity | `git status`（**長形式**）中心。`git status -s` も混在 | 25.1% | ❌ |

  corpus 別に見るとばらつきはさらに大きい（v2 compact は同一）。

  | corpus | claude no-skill | codex no-skill | v2 compact | claude 削減 | codex 削減 |
  |---|---:|---:|---:|---:|---:|
  | small | 542 | 248 | 229 | 67.2% | 7.3% |
  | medium | 563 | 4706 | 666 | **-18.3%** | 85.8% |
  | large | 3688 | 4220 | 2217 | 39.9% | 47.4% |

  原因は2つある。

  1. **エージェントが選ぶ形式が platform ごとに違う**。claude は porcelain
     （compact と同じ1項目1行の機械可読形式）を選ぶため分母が小さく、削減が出ない。
     agy は長形式を選ぶため分母が大きい。`SI-FLW-007` は
     「`--porcelain=v2` は `flow.py` 自身が parse に使う形式なので分母にするのは公正さを欠く」
     として固定 baseline から除外したが、**案A では エージェントが自発的に porcelain を
     選ぶため、除外したはずの形式が分母に戻ってきている**。
  2. **同じ情報を何回取得したかが分母に乗る**。harness は `no-skill` 条件の
     raw コマンド出力を**連結**して分母にする（`run_codex.py` の `_task_output`）。
     codex は同じ情報を2コマンドで取るため分母が約8倍に膨らみ（medium: 4706 B）、
     結果として削減率が高く出る。**冗長に叩いた platform ほど有利**という逆転が起きている。

  つまりこの指標が現在測っているのは compact renderer の性能ではなく、
  「`no-skill` のエージェントがたまたま何回・どの形式で叩いたか」である。
  `FLW-NFR-002` の閾値 70% の妥当性以前に、**分母の定義が測定として成立していない**。

  なお `diff-summary` は分母が固定（生 unified diff）のため3 platform とも
  88.5〜89.0% で安定しており、閾値 80% を満たす。問題は `dirty-status` に限る。

- **提案する修正**: 次のいずれか、または組み合わせを裁定する。
  1. **重複取得を正規化する**。`no-skill` の分母を「連結」ではなく
     「同一情報を得る最小の1コマンドの出力」とする（複数回叩いた場合は最大 or 最初の1件）。
     冗長さが有利にならない。
  2. **platform ごとに評価する**。`FLW-NFR-001` の SFCR が「platform 別に判定し
     全体平均で相殺しない」と定めるのと同様に、byte 削減も platform 別に判定する。
     ただし現状は platform 別に見ても claude 5.9% / agy 25.1% で未達のため、
     これ単独では解決しない。
  3. **固定 baseline へ戻す**。`SI-FLW-007` が退けた案だが、案A が
     「エージェントの気まぐれ」を分母に持ち込むことが実証されたため再検討に値する。
     公正さの論点（`--porcelain` を分母にしてよいか）は残る。
  4. **`dirty-status` の価値指標を byte から変える**。compact と porcelain が
     同じ1項目1行である以上、byte 削減は原理的に大きくならない。`dirty-status` の価値は
     「必須 field 保持・blocking 項目保持・gate 遵守・cross-model の判断一致」にあり、
     `FLW-NFR-002` の他の受入基準が既にそれを測っている。**`dirty-status` の byte 閾値のみ
     supersede で外す / 緩める**案。
  5. 上記のいずれでも `FLW-NFR-002` の受入基準の意味を変えるため **supersede が必要**。
     `SI-FLW-007` の裁定6「削減率を緩める場合でも必須 field 保持 100% と
     blocking 項目保持 100% は緩めない」は維持する。

- **対象ファイル**: `.spec/requirements/FLW-NFR-002.md`（supersede する場合）、
  `.spec/discovery/metrics.md`（Token / Output Efficiency の測定条件）、
  `evals/flow-core/m0-eval/score.py`（分母の算出）、
  `evals/flow-core/m0-eval/run_codex.py` の `_task_output`（連結の是非）、
  `evals/flow-core/m0-eval/README.md`（測定条件節）。

- **確認観点**:
  - 重複: `SI-FLW-007` は「測定条件が未定義」で accepted 済み。本 issue は
    **その裁定（案A）を実測した結果その定義に欠陥が見つかった**という後続であり、
    重複ではなく follow-up である。
  - 既存要件との関係: `FLW-NFR-002` は implementing で EARS 節が書き換え不可のため、
    閾値・測定条件のいずれを変えるにも supersede が必要。
  - ガードレール: **数値を通すために分母を大きい方へ選び直さない**。案の採否は
    「何を測りたいか」から導き、実測値の有利不利で決めない。
  - 検証: 採用案で `score.py` を修正し、既存 270 trial のデータを再採点して
    platform 間のばらつきが縮むことを確認する（再実測なしで検証できる）。
  - 軽量レーン適否: **不適**（M0 出口条件の合否を左右し、要件の supersede を伴う）。

- **影響推定・ロールバック**: 案1・2 は `score.py` の変更に閉じ、実装コードに触れない。
  既存 trial JSONL を再採点できるため再実測不要。案4 は `FLW-NFR-002` の supersede を伴う。
  いずれも単独 revert できる。

- **依存**: `SI-FLW-007` の follow-up。`FLW-TSK-012` の M0 出口判定を塞いでいる3件のうちの1つ。

- **実施**: 2026-08-05 `FLW-NFR-008`（`FLW-NFR-002` の supersede）を起票し、`FLW-TSK-015`（done）で
  案3 + 案4 を実装した（PR #164、コミット `0d0bc0d`）。分母を固定 baseline
  （`dirty-status` = `git status` 長形式、`diff-summary` = 生 unified diff）へ戻し、
  `score.py` は fixture から分母を取るようにした。閾値は `dirty-status` 40% / `diff-summary` 80%。
  既存 270 trial の再採点で platform 間のばらつきが 69.1pt → 2.8pt に縮み、3 platform とも閾値を満たした。
