---
id: SI-FLW-075
raised_by: FLW-REV-019（BIZ-102 / OPS-101 / OPS-103 / RSK-402 / OPS-201 / OPS-203 / OPS-302）
target: 証跡の粒度と、失敗系 result の空欄
proposed_change_type: modify
status: accepted
---
- **目的**: 証跡が「記録されている」ことと「主張を裏づけている」ことの乖離を解消する。

- **発見した事実**:
  1. **出口条件7の実走が証跡化されない**（`BIZ-102`）— `FLW-NFR-011` の証跡は今回も
     0.02 秒のゲート照合1件であり、3platform 実走そのものではない
  2. **raw log の保存成否が Gate 判定に未接続**（`OPS-101`）— 保存 root も証跡から特定できない
  3. **attempt 台帳が coordinator / lease / hash-chain / attempt ID を持たない**（`OPS-103`）—
     台帳と run の結び付けも手作業
  4. **confirmation 側の検出器に対照実験が無い**（`RSK-402`）— 測定自体がフェイルオープンで、
     residual は hazard と同一式のまま
  5. **失敗系 result が空**（`OPS-201`）— worktree write の失敗系は cause も
     `recovery_class` も `next_actions` も空。**今回新設した fail-closed BLOCKED も同じ穴**
  6. **audit が出荷面で届かない**（`OPS-203`）— `UNSUPPORTED` のため運用者は事故後に
     この診断へ到達できない。「library として成立・運用者未到達」という判定の分離も未記録
  7. **裁定スコープの allow に失効・撤去・登録の機構が無い**（`OPS-302`）

- **提案する修正**: confirmation の実走そのものを証跡化し、raw log の保存成否を Gate 判定へ
  接続する。失敗系 result に cause / `recovery_class` / `next_actions` を載せる。
  裁定スコープ allow に失効期限を持たせる。

- **対象ファイル**: `evals/flow-core/m2-eval/run_local_confirmation.py`、
  `flowlib/cli.py`、`scripts/agy_guard.py`、`tests/`

- **確認観点**: 検出器に陽性・陰性対照を置く。失敗系 result が空欄でないことを機械検査する。

- **依存**: 出口条件7の判定に関わる。
