---
name: skill-improver
description: evals/observations/observations.jsonl に蓄積された観察ログ（skill-observerが記録）をIngest→Inspect→Propose→Amend→Evaluateの手順で分析し、繰り返し起きている問題から改善提案を作る。.spec/ があるリポジトリでは直接修正せず .spec/spec-issues/ へ起票し、人間の裁定（要件化）後に SKILL.md を修正する。「観察ログを分析して」「溜まったフィードバックでスキルを改善して」「自己改善サイクルを回して」と言われた場合や、openな観察が蓄積した場合に使用する。構造的な最適化はskill-optimizer、修正後の検証はskill-validatorと連携する。修正のコミットは行わない（人間が行う）。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-07"
  updated: "2026-07-11"
---

# skill-improver

## 目的

`skill-observer` が蓄積した観察ログを分析し、スキルの記述そのものを修正する
ことで自己改善ループを閉じる。観察（事実の採取）は observer、改善（修正の
実行）はこのスキル、という分担。

## 原則

- **繰り返しを直す**: 1回きりの事象より、同じスキル・同じステップで繰り返し
  起きている問題を優先する
- **過学習を避ける**: suggested_fix は出発点にすぎない。特定ケースだけに
  効く文言追加ではなく、一般化した修正にする
- **修正は1スキルずつ**: 影響範囲を確認しながら進め、まとめて雑に変えない
- **提案と実装の分離**: 対象リポジトリに `.spec/` がある場合、修正の前に
  `.spec/spec-issues/` への起票と人間の裁定（要件化 draft → approved）を必須とする。
  「自動修正はコミット前に人間が diff 確認」のガードレールを、プロンプト依存から
  `.spec` の状態遷移による機械検証可能な形に昇格させる
- **コミットは人間が行う**: このスキルは修正とログ更新までを行い、
  git commit はしない。自動化と責任の境界を守る

## ワークフロー

### 1. Ingest（ログ取得）

カレントプロジェクトの `evals/observations/observations.jsonl` から
`status: "open"` の行を読み込む。0件ならその旨を報告して終了する。
他プロジェクトで収集したログがあれば、先に行単位で連結して統合する
（書式の正典は skill-observer の observation-schema.md）。

### 2. Inspect（パターン抽出）

open な観察をスキル別・ステップ別に集計し、severity と件数で優先順位を
つける（集計と優先順位の基準は `references/improvement-cycle.md`）。
修正対象の候補と根拠（該当する観察の要旨）を一覧で提示し、
どれを修正するかユーザーと合意する。

### 3. Propose（spec-issue 起票 — .spec/ があるリポジトリでは必須）

対象リポジトリのルートに `.spec/` がある場合、Step 2 で特定した修正候補を
**直接修正せず `.spec/spec-issues/` に1件ずつ起票**する（書式は bitz-sdd `sdd-core` の
assets/spec-issue.md。`raised_by: skill-improver`、根拠として該当する観察ログの
要旨と件数を明記）。人間が spec-issue を裁定して要件化（draft → approved）するまで
Step 4 に進まない。`.spec/` がないリポジトリでは、従来どおり Step 2 の一覧について
ユーザーと直接合意すれば Step 4 に進んでよい。

### 4. Amend（修正実行 — 裁定後）

裁定・合意した対象を1スキルずつ修正する。

- 対象スキルの SKILL.md（必要なら references/）を、観察された事実が
  再発しないように修正する
- 修正したスキルは `metadata.version` を semver で bump し、
  `metadata.updated` を当日にする。プラグイン配下ならプラグイン version の
  bump も必要なことを報告に含める
- description の発動精度や本文の構造に踏み込む改善が必要な場合は、
  その部分を `skill-optimizer` に委ねる
- 対象スキルの SKILL.md が見つからない（ライブラリ外・削除済み等）場合は
  修正せず、Step 6 でその旨を報告する

### 5. Evaluate（検証）

修正した各スキルを `skill-validator` で検証する。critical / high 起因の
修正や description を変えた場合は、`skill-tester` → `skill-evaluator` での
再テストも提案する。

### 6. ログ更新と完了報告

- 対応した観察の `status` を `"resolved"` に、対応しないと判断した観察は
  `"wontfix"` に更新し、`resolved_by` に日付と対応の要旨を記入する
  （更新してよいのは status / resolved_by のみ）
- 修正したスキルと版数の一覧・残った open 件数・スキップした観察を報告し、
  **コミットはユーザーに委ねる**（diff の確認を促す）

## 詳細

集計テンプレート・優先順位の基準・status 遷移・過学習を避ける修正の指針は
`references/improvement-cycle.md` を参照。
