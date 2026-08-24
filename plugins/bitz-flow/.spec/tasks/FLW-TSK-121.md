---
implements: FLW-FR-006
depends_on: [FLW-TSK-120]
boundary: plugins/bitz-flow/.spec/requirements/FLW-FR-006.md,plugins/bitz-flow/.spec/requirements/FLW-NFR-014.md,plugins/bitz-flow/.spec/specs/m2-local-safety-profile/test-spec.md,plugins/bitz-flow/skills/flow-core/references/m2-operability-coverage.json,tests/test_flow_m2_operability.py,plugins/bitz-flow/.spec/reports/m2-unconnected-points.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### fixture検証とproduction接続を区別し証跡の過大主張を解消する

`SI-FLW-090`（`FLW-REV-027:SYN-007` P1）。`SI-FLW-084`〜`089`の是正が完了し、
残るのは**証跡と実態の整合**である。

- **実測した過大主張**:
  - `FLW-NFR-014`の検証手段が「Linux・macOS・Windowsの登録済みlocal filesystem
    **fixture**で通常系`UNSUPPORTED` 0件を出口条件とする」と書いており、
    **fixture上の成立を出口条件に据えている**。実環境観測を要求していない。
  - `m2-operability-coverage.json`は受入行とE2E edgeにtestを対応づけるが、
    **その testが実在するかも、production経路かfixture注入かも検査していない**
    （`test_coverage_manifest_covers_every_acceptance_row_and_flow_edge`は
    キーの網羅と値の非空しか見ない）。
  - `FLW-FR-006`はcreate/resumeの是正taskへ直接トレースしておらず、
    `finish`／`discard`がM3送りである境界も受入基準から読めない。
- **作業内容**:
  - coverage manifestを`contract_version: 2`へ上げ、各entryへ`connection`
    （`production`／`fixture`）を持たせる。検査testを、**cited testの実在**と
    `production`宣言のtestがhandler注入を使っていないことまで見るよう強化する。
  - test-specへ実環境probe・production dispatcher・timeout・crash境界・recovery分類の
    導出行を追加し、fixture内部検証とproduction接続を**列で区別**する。
  - `FLW-NFR-014`の検証手段からfixture出口条件を外し、実環境probeとproduction
    black-boxをverified条件に据える。
  - `FLW-FR-006`へ`FLW-TSK-115`／`116`を直接トレースし、`finish`／`discard`が
    M3であることを受入基準へ明示する。
  - `FLW-TSK-106`〜`114`の未接続点を`.spec/reports/m2-unconnected-points.md`へ
    集約記録する（taskの`done`は取り消さない。裁定
    `.spec/reports/decision-2026-08-24-flw-nfr-014-reopen.md`に従う）。
- **完了条件**:
  - coverage manifestが名指しするtestがすべて実在すること（機械検査）。
  - `production`宣言のentryがfixture注入testを含まないこと（機械検査）。
  - `verified`昇格条件がfixture成立ではなくproduction証跡になっていること。
  - 最終レビューPASS前にPromotion Gateを通さないことが明記されていること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: `SI-FLW-084`〜`089`の完了後。runtime挙動は変えない。
