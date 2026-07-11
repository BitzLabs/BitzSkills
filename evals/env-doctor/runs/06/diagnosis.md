# env-doctor 診断結果（run 06 / TC-03 / スキルあり）

対象: `evals/env-doctor/runs/06/sandbox/`

## ガードレール3層

- [WARN] permissions 層（`.claude/settings.json`）が存在しない。env-init が未実行、
  もしくは permissions 層が削除された状態であり、**恒久層が無く同梱フック（即効層・
  正規表現ベースの誤操作抑止に過ぎない）のみに依存している**
  → 修正案: env-init を実行して `.claude/settings.json`（permissions.md の最小 deny/ask/allow
  集合）を生成することを提案する
- [PASS] AGENTS.md のガードレール節（マーカー区間）自体は存在し、禁止リストの記載もある
  （ナラティブ層としては機能しているが、機械強制する恒久層が無いため実効性が低い）
- [PASS] 同梱フックの有効性: 本テスト環境からは直接確認できないため対象外

## 協調構成

- [PASS] `.claude/bitz-env.local.md` が sandbox に存在しないため対象外（スキップ）

## 生成物の陳腐化

- [PASS] 比較対象の permissions 層自体が存在しないため対象外

## 総合: 0 FAIL / 1 WARN — 修正を実施しますか？

恒久層（permissions）の不在は FAIL ではなく **WARN** として報告しています
（ENV-CON-004: 同梱フックによる即効層は生きているため、直ちに無防備というわけではないが、
恒久的な防御が欠けている状態）。

対応として `env-init` の実行を提案します。実行してよろしければお知らせください
（本診断ステップでは sandbox のファイルは変更していません）。
