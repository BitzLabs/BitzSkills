---
implements: FLW-NFR-011
depends_on: [FLW-TSK-051]
boundary: evals/flow-core/m1-eval/qualification-runs/, evals/flow-core/m1-eval/README.md
status: done
---

### 3 platformでqualificationを実走しactive manifestを発行する

- **作業内容**: 前タスクの runner を使って **3 platform で qualification を実走**し、
  結果を成果物として記録する。

  - 実行結果（manifest・raw log digest・所要時間・再試行回数）を
    `evals/flow-core/m1-eval/qualification-runs/` へ保存する。
  - 3 platform すべてが `PASS` した場合にだけ **active manifest** として記録する。
    1 platform でも FAIL / BLOCKED なら active にしない（平均で相殺しない）。
  - `evals/flow-core/m1-eval/README.md` に実走の条件（CLI version・model identity・
    host event-contract version・実行日時）と結果を記録する。M0 の `m0-eval/README.md` に倣う。
  - **合成の運用コスト実績**（台帳の整合検査・失効判定の保守にかかった手数）を
    run manifest へ記録する。M1-5 の ROI 見積もりで積み残した項目であり、
    M2 以降の budget 再校正の材料とする。

- **完了条件**: 3 platform 分の manifest が qualification manifest schema を満たし、
  `gate_status` が記録されていること。PASS した場合は active manifest が1つだけ存在すること。
  README に実走条件と結果が記載されていること。
  `python3 <リポジトリ>/scripts/release_check.py` と canonical spec inspect が PASS すること。

- **備考**: 本タスクは M1-6 の出口判定である。**被測定物（M1 operation）の confirmation は
  含まない**（裁定: `.spec/reports/decision-2026-08-12-m1-6-scope.md`）。
  M1 operation は引き続き `UNSUPPORTED` であり、active manifest が示すのは
  「計測器が 3 platform で適格である」ことに限られる。
  実走が失敗した場合は原因を記録し、Gate を `blocked` のまま人間へ再提示する
  （失敗を隠して active にしない）。
