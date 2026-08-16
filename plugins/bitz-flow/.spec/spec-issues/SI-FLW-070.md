---
id: SI-FLW-070
raised_by: FLW-REV-018（OPS-403 / OPS-105 / BIZ-101 / BIZ-102 / OPS-103 / OPS-101 / BIZ-201 / RSK-402）
target: 検証証跡の到達可能性・TTL 時限故障・比率 field の非測定
proposed_change_type: modify
status: accepted
---
- **目的**: 証跡が「記録されている」ことと「裁定者が辿れる」ことの乖離を解消する。
  あわせて **CI の時限故障**を取り除く。

- **発見した事実**:
  1. **TTL 時限故障（最優先）**（`OPS-403`）— コミット済み qualification が
     **2026-08-17T07:45:25Z に失効**する。`--verify-for-gate` の exit 0 を主張する
     テストが CI にあるため、**コード変更が無くても時刻が過ぎるだけで全ブランチが赤になる**。
  2. **証跡 commit が到達不能**（`OPS-105` / `BIZ-101`）— `.spec/verification/` の4件が
     すべて **HEAD の祖先でない commit** を指す。squash merge で SHA が変わるためで、
     M0 期の証跡も同様。**構造的欠陥であり今回持ち込んだものではない**。
  3. **証跡の粒度が要件に届かない**（`BIZ-102`）— 出口条件7（3 platform confirmation）の
     証跡として記録されたのは 0.02 秒の `--verify-for-gate` であり、実走そのものではない。
  4. **attempt 台帳の結び付けが手作業**（`OPS-103`）— coordinator・lease・hash-chain・
     attempt ID が無く、manifest から参照されず、台帳名も手でリネームしている。
  5. **比率 field が全段で定数**（`BIZ-201` / `RSK-402` / `OPS-101`）—
     `required_checks` / `positive_controls` は subject・runner・manifest のすべてで
     同じ定数を運ぶだけで、台帳が無い。raw log の保存成否・canary も Gate 判定に未接続。

- **提案する修正**:
  - TTL 検査を「証跡が有効であること」ではなく「**失効していたら再実走を促す**」形にし、
    CI が時刻で赤にならないようにする（あるいはテストを TTL 非依存にする）
  - 証跡へ squash 後の commit を後追いで書ける仕組み、または commit ではなく
    tree digest / tag で紐づける方式を検討する（`spec_verify` 側の課題として bitz-sdd へ委託も可）
  - confirmation の実走そのものを証跡化する
  - required check / 陽性対照の ID 台帳を test-spec に定義し、件数を収集結果から導出する

- **対象ファイル**: `evals/flow-core/m2-eval/run_local_confirmation.py`、
  `evals/flow-core/m2-eval/local_confirmation_subject.py`、`tests/test_flow_m2_confirmation.py`、
  `plugins/bitz-flow/.spec/specs/m2-runtime/test-spec.md`

- **確認観点**: 時刻を進めても CI が赤にならないこと。証跡の commit が確定 ref から辿れること。

- **影響推定・ロールバック**: 1 の TTL 時限故障は**期限があるため独立に先行させてよい**。

- **依存**: 出口条件7の判定に直結する。
