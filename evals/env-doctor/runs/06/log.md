# run 06 — TC-03 / スキルあり

- **ケースID**: TC-03
- **モード**: スキルあり（env-doctor SKILL.md を読んだ上で忠実に実行）
- **実行日時**: 2026-07-11
- **入力プロンプト**: 「ガードレールがずれてないか確認して」
- **sandbox**: `evals/env-doctor/runs/06/sandbox/`（`.claude/settings.json` が存在しない
  ＝ env-init 未実行相当の前提条件を注入。AGENTS.md のみ存在）

## 手順の記録

1. SKILL.md の診断項目1・4行目
   「env-init が未実行で permissions 層（`.claude/settings.json` の deny）が存在しないかを確認し、
   無ければ『恒久層なし・同梱フックのみに依存』を **WARN** として報告する」に従い、
   sandbox に `.claude/settings.json` が存在しないことを確認
2. FAIL ではなく WARN として明示的に分類（SKILL.md がこの区別を明文で指示しているため
   曖昧さなく判定できた）
3. 対応として env-init の実行を提案（SKILL.md 本文で env-init との関係が明記されているため
   固有名詞で誘導できた）
4. 診断結果を `runs/06/diagnosis.md` に保存。ファイルの変更は行っていない

## 成果物一覧

- `runs/06/diagnosis.md`
- `runs/06/log.md`（本ファイル）

## 備考

- ベースライン run05 は「恒久層なし」を事実として言及できたが、WARN という重大度ラベルの
  明示と env-init という具体的な次アクションの提案はできなかった。
  run06（スキルあり）はSKILL.mdの明文規定によりこの2点を明確化できた
