---
implements: FLW-NFR-011
depends_on: []
boundary: evals/flow-core/m1-eval/compatibility.py, tests/test_flow_m1_compatibility.py
status: done
---

### compatibility key v1と失効規則

- **作業内容**: `evals/flow-core/m1-eval/compatibility.py` に compatibility key を実装する。

  - **閉集合13要素**を canonical JSON 化して digest を作る: scoring rule / runner / adapter /
    oracle / fixture / prompt / skill / result・event schema / 推移的依存 / model identity・date /
    CLI version / host event-contract version / trial 割付。
  - **欠落・未知 field は互換と見なさない**（`blocked`）。「知らない field があるが他は同じだから互換」
    という判断をしない。
  - credential・rate-limit 残量などの**短命状態は key に含めない**。合成直前の
    dynamic fingerprint で再照合する。
  - **`evidence_id` と分離**する（raw log digest・attempt ID・run 固有 metadata は別）。
  - **失効規則**: scoring rule / fixture / prompt / schema / runner 共通部が変われば
    **全 platform 証跡を失効**、platform adapter だけが変われば**当該 platform だけ失効**。

- **完了条件**: 単体テストが PASS し、次が確認できること —
  同じ入力から同じ key が出ること（決定論）、field を1つ変えると key が変わること、
  欠落・未知 field が `blocked` になること、短命状態が key に影響しないこと、
  共通入力の変更で全 platform が失効し adapter の変更で当該 platform だけが失効すること、
  `evidence_id` が key に混ざらないこと。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: M0 の実測では harness を触った 18 commit のうち 4 件（22%）が単一 platform の
  adapter 修正であり、失効規則の粒度がそのまま再実測コストに効く
  （ROI 判定: `.spec/reports/decision-2026-08-12-m1-5-roi.md`）。
