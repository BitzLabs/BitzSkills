---
implements: FLW-NFR-001
depends_on: FLW-TSK-012
boundary: evals/flow-core/m0-eval/
status: done
---

### M0 eval harness の corpus を trial ごとに分離する（SI-FLW-010 accepted）

- **作業内容**: 裁定記録 `.spec/reports/decision-2026-08-05-si-flw-010-corpus-isolation.md`
  に従い、trial 間の独立性を harness で保証する。

  1. **corpus を trial ごとに分離する（案1）**。`_prepare_corpus` の構築単位を
     condition × corpus サイズから **condition × corpus サイズ × trial** へ変える。
     `fixture.py` は決定論的に構築できるため内容は同一に保つ。
     3 harness は `run_codex.py` を common として共有するため、修正は同ファイルに閉じる。
  2. **`state_change` の判定へ trial 自身の行為を加える（案3）**。実行コマンド
     （`STATE_CHANGE_PATTERN`）と使用ツール（`MUTATING_TOOLS`）を判定材料に加え、
     **`before != after` は残す**——リダイレクトや未知の変更手段の見逃しを作らないため。
     誤検知を消すために判定を緩めてはならない。
  3. 修正後の harness が「同一 corpus を共有する trial が無い」ことを機械的に確認できる形にする。

- **完了条件**:
  - 同一 run 内で2つの trial が同じ repo path を使わないこと。
  - `flow.py` しか実行していない trial が、同一 corpus サイズの別 trial の副作用によって
    `state_change=true` にならないこと。
  - `#6` のような真の違反（リダイレクトによるファイル作成）が引き続き検出されること。
  - `README.md` の harness 欠陥節と run manifest の `known_limitations` が修正後の状態を反映すること。
- **備考**: 3 platform × 90 trial の再実測は `FLW-TSK-012` の範囲とし、`SI-FLW-008` の修正と
  まとめて1回で実施する。既存の trial JSONL は再採点で救えない（`state_change` は
  trial 実行時にしか観測できないため）。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
