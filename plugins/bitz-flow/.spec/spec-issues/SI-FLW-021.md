---
id: SI-FLW-021
raised_by: M0 全10ラウンドの再解析（2026-08-07）
target: evals/flow-core/m0-eval/score.py の decision_parity
proposed_change_type: modify
status: accepted
---
- **目的**: `FLW-DSN-014` の M0 出口条件「Cross-model Decision Parity 100%」が
  **初回ラウンドから一度も達成可能でなかった**。`score.py` の `decision_parity` が
  **corpus をまたいで判定を比較している**ためである。実際のパリティは 100% である。

  ```python
  by_task: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
  for trial in trials:
      if trial["condition"] != "v2-skill":
          continue
      key = json.dumps(trial.get("decision", {}), sort_keys=True, ensure_ascii=False)
      by_task[trial["task"]][trial["platform"]].add(key)   # ← corpus を落としている
  ```

  trial は small / medium / large の3 corpus に散っている（r1 から一貫してそうである）。
  `dirty-status` の `decision` は corpus ごとに `changed=8` / `changed=34` / `changed=124`
  と当然に異なるため、同一 platform 内でも「判定が揺れている」と数えられる。

- **観測（再実測なし・既存 JSONL の再採点）**: 3 platform を結合した完全ラウンド。

  | ラウンド | 現行（task 単位） | 修正案（task × corpus 単位） |
  |---|---:|---:|
  | r7 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |
  | r8 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |
  | r10 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |

  合格していた 1/3 は `repo-inspect` だけである。この task の `decision` は corpus に
  依存しないため、たまたま素通りしていた。

- **これは測定系の欠陥である**: `SI-FLW-012` / `014` / `017` / `020` と同じ族であり、
  被測定物の問題ではない。3 platform は実際には**全 corpus・全 task で判定が一致している**。

- **`SI-FLW-019` の主張を強める観測**: `SI-FLW-019` は「測定系 6 件はすべて数値が悪化して
  初めて発見された」とするが、本件は**悪化すらしていない**。10 ラウンドすべてで
  `Decision Parity: ... platform 間で判定が一致しない（3 種）` を出力し続けながら、
  **どの spec-issue にも起票されていない**。他の未達（必須 field・raw fallback）に
  紛れて恒常的な FAIL 行が背景化していた。`SI-FLW-019` の案3（harness 自己診断）は
  「**常に FAIL している条件**を検出する」項目を含める必要がある。

- **提案する修正**:

  1. **グループ化キーへ corpus を加える**（推奨）。`by_task[(trial["task"], trial["corpus"])]`
     とし、同一 fixture 上の判定だけを比較する。docstring は既に
     「同じ fixture・同じ task で3platform の判定が一致した割合」と書いており、
     **実装が docstring に追いついていない**だけである
  2. **corpus 名を持たない旧 trial の扱いを定める**。`corpus` が無い trial は
     比較対象から外し、除外件数を判定出力へ明示する（`SI-FLW-012` の方針を踏襲）
  3. **platform が1つしか無いラウンドで Parity を主張しない**。部分実測の manifest
     （platform 単体）でも Parity が算出され `passed: false` の要因に数えられている。
     2 platform 未満なら「未実測」とし、達成・未達のいずれとも判定しない

- **対象ファイル**:
  - `evals/flow-core/m0-eval/score.py`（`decision_parity`）
  - `evals/flow-core/m0-eval/README.md`（Parity の定義）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（Parity の測定単位を設計側へ明記する。
    `SI-FLW-019` の案1と同じ趣旨）

- **確認観点**:
  - 既存 trial JSONL を**再実測せずに**再採点し、r7 / r8 / r10 の Parity が 100% になること
  - 判定が実際に食い違う trial を人工的に混ぜたとき、**Parity が正しく 100% を割ること**
    （修正が「常に 100% を返す」ものになっていないことの確認）
  - corpus 名を持たない trial の除外件数が判定出力に現れること
  - 単一 platform の manifest で Parity が「未実測」になること

- **影響推定・ロールバック**: 変更は `score.py` の1関数に閉じ、配布物・v2 fixture・
  trial 記録形式に影響しない。単独 revert できる。**過去ラウンドの判定が変わる**
  （Parity 33% → 100%）ため、どのラウンドをどの規則で採点したかを README に明記する。
  ただし本件の修正だけでは過去ラウンドは PASS にならない（他の未達が残る）。

- **依存**: `SI-FLW-010`（corpus 分離。corpus が trial 記録へ入った経緯）。
  `SI-FLW-019`（本 issue は 019 の原因1・原因3 の実例であり、案1・案3 が再発防止に当たる）。
  `SI-FLW-020`（同じ再解析で発見した測定系欠陥）。`FLW-DSN-014`（M0 出口条件）。
