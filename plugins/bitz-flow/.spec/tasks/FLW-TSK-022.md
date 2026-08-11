---
implements: FLW-NFR-009
depends_on: [FLW-TSK-021]
boundary: evals/flow-core/m0-eval/score.py,tests/test_m0_eval_scoring.py
status: done
---

### 採点規則・入力digestとmanifestライフサイクルを実装する

- **作業内容**:
  - 全runner、fixture、score、公開schemaを含む採点規則digestを実装する。
  - trial集合、raw log、再導出observationの入力digestと複合`result_id`を実装する。
  - legacy manifestの冪等移行と`unknown/candidate/active/revoked`状態機械を実装する。
  - 有限timeout付きOS lock、一時file、file/directory fsync、原子的置換を実装する。
  - active entryの一意性、blocked縮退、不正遷移拒否を回帰で固定する。
- **完了条件**: 採点依存の単独変更で規則versionが変わり、非依存fileでは変わらないこと、
  並行更新・中断・legacy移行・復旧の回帰がPASSする。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
