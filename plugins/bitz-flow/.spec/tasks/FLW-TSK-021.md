---
implements: FLW-NFR-009
depends_on: []
boundary: evals/flow-core/m0-eval/run_codex.py,evals/flow-core/m0-eval/run_claude.py,evals/flow-core/m0-eval/run_antigravity.py,tests/test_m0_eval_scoring.py
status: done
---

### 共通envelope観測とtruncation検証を実装する

- **作業内容**:
  - published codeと期待operationを照合する共通envelope抽出器を追加する。
  - preamble、候補なし、別operation、複数候補をfail-closedで観測へ記録する。
  - selected envelope block内だけでitemと`TRUNCATED shown=N total=M`を解析する。
  - 全量時は全item、省略時は集計値・shown/total・表示済みitemをoracleと照合する。
  - proxy台帳の`PXY-001`〜`PXY-014`とharnessのID集合を一致させる。
- **完了条件**: true positive、false positive防止、false negative防止を含む対象pytestがPASSし、
  `SI-FLW-036`の2事例をfixture化した回帰がPASSする。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
