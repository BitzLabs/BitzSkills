---
implements: FLW-NFR-008
depends_on: FLW-TSK-012
boundary: evals/flow-core/m0-eval/, plugins/bitz-flow/.spec/discovery/metrics.md, tests/fixtures/flow/byte-manifest.json, tests/test_flow_contract.py
status: done
---

### byte 削減の分母を固定 baseline へ変更する（SI-FLW-009 accepted）

- **作業内容**: 裁定記録 `.spec/reports/decision-2026-08-05-si-flw-009-byte-denominator.md`
  に従い、byte 削減の分母をエージェントの挙動から切り離す。

  1. **`fixture.py` の `BASELINE_COMMANDS` へ `dirty-status` を追加**する
     （`git status`、引数なしの長形式）。parse 入力である `--porcelain` 系は分母にしない。
  2. **`score.py` の分母を fixture から取る**。trial の記録ではなく `baseline_table()` が
     fixture を決定論的に構築して測る。旧 JSONL も新 JSONL も同じ定義で採点できるようにする
     （検証を既存 270 trial の再採点で行うため、この性質が要る）。
  3. **削減率は trial ごとに算出して median を取る**。corpus 規模ごとに分母が違うため、
     median 同士を割ると規模の違う corpus が混ざる。
  4. **閾値を `dirty-status` 40% / `diff-summary` 80% にする**。
  5. harness は trial 行へ自 task の `raw_baseline_bytes` を記録する（従来は
     `diff-summary` のみ）。`metrics.md` と `README.md` の測定条件節、
     `byte-manifest.json` / `test_flow_contract.py` の要件 ID 参照も更新する。

- **完了条件**:
  - 既存 270 trial を再採点し、`dirty-status` の platform 間のばらつきが縮むこと。
  - 3 platform とも `dirty-status` 40% 以上・`diff-summary` 80% 以上を満たすこと。
  - `truncated: false` の trial だけを対象とする規律を維持していること。
  - 数値を通すために分母を大きい方へ選び直していないこと（分母は長形式に固定し、
    `--porcelain=v2` は採らない）。
- **備考**: 再採点で検証できるため**再実測は不要**。3 platform × 90 trial の再実測は
  `SI-FLW-008` / `SI-FLW-010` の修正確認として `FLW-TSK-012` が別途行う。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
