---
implements: FLW-NFR-011
depends_on: []
boundary: evals/flow-core/m2-eval/run_local_confirmation.py, evals/flow-core/m2-eval/record_run.py, evals/flow-core/m2-eval/active-local-confirmation.json, tests/test_flow_m2_confirmation.py
status: pending
---

### confirmation の実走そのものを証跡化し raw log 保存成否を Gate へ接続する

- **作業内容**: 出口条件7の証跡は 0.02 秒のゲート照合1件であり、3 platform の実走そのものでは
  なかった。「実走した」という主張と「実走の証跡がある」ことが乖離している。
  `FLW-DSN-014` の改訂に従い是正する。
  - **実走の証跡**: trial ごとに開始・終了時刻、platform と CLI 版、被測定物の commit、
    実行コマンドの正規形を記録する。ゲート照合の記録で代替しない。
  - **raw log**: 保存の成否を証跡へ書き、保存先 root を証跡から特定できるようにする。
    保存に失敗した trial を Gate 判定で PASS にしない。
  - **attempt 台帳**: coordinator ID・lease・hash chain・attempt ID を持たせ、台帳と run を
    機械的に結び付ける。手作業の対応付けを残さない。
  - **検出器の対照実験**: confirmation 側の検出器に陽性対照を置き、検出0件と検出器不作動を
    区別できるようにする。現状はフェイルオープンである。
  - **residual**: `hazard` と同一式で算出した値を残余リスクとして提示しない。緩和後に残る量を
    別の観測から算出するか、算出できないなら報告しない。
  - **裁定スコープの allow**: 失効期限・撤去手段・登録者を持たせる。期限の無い allow を残さない。
- **範囲外**: 実行環境ガード本体の是正（別タスク）。M2 出口条件の再判定（是正後の独立レビュー）。
- **検証**: 保存失敗を注入した trial が PASS にならないこと、検出器の陽性対照が実際に検出すること、
  期限切れ allow が拒否されることをテストで確認する。台帳と run の結び付きが機械的に辿れることを示す。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
