---
name: skill-instrumenter
description: 監視したいエージェントスキルのSKILL.mdに、skill-observerによる自己観察ステップを注入（計装）または除去する。「このスキルにobserverを追加して」「スキルを監視対象にして」「自己観察を組み込んで」「計装して」「計装を外して」と言われた場合に使用する。観察の実行はskill-observer、蓄積ログの分析・改善はskill-improverが行う。
metadata:
  version: "0.1.1"
  author: br7.hide
  created: "2026-07-07"
  updated: "2026-07-15"
---

# skill-instrumenter

## 目的

監視対象にしたいスキルの SKILL.md 末尾に、マーカーで囲んだ「自己観察」
セクション（`skill-observer` の呼び出し指示）を追記する。これにより、
そのスキルが実行されるたびに最後へ自己観察が入り、問題が観察ログに蓄積される。

このスキルの責務は「観察ステップの注入と除去」のみ。どのスキルでも計装できる
（BitzSkills ライブラリ外のスキルも可）。

## ワークフロー

### 1. 対象スキルの特定

ユーザーに監視したいスキルを確認する（複数可）。スキル名だけ指定された場合は
SKILL.md のパスを探して提示し、合意してから進める。

### 2. 計装状態の確認

対象 SKILL.md 内のマーカー `<!-- bitzskills-observer:start -->` の有無を調べる。

- **マーカーなし** → Step 3（注入）
- **マーカーあり・内容が最新テンプレートと同じ** → 計装済みと報告してスキップ
- **マーカーあり・内容が古い** → マーカー間を最新テンプレートで置き換え、Step 4 へ

### 3. 観察ステップの注入

`references/instrumentation-guide.md` のテンプレートを、SKILL.md 本文の
**末尾**にそのまま追記する。テンプレートの文言は変更しない
（除去・更新がマーカー頼みのため、書式を揃える必要がある）。

### 4. metadata の更新

計装は SKILL.md の内容変更なので、対象スキルの `metadata.version` を
**patch** で bump し、`metadata.updated` を当日にする。

対象がプラグイン配下（`plugins/<name>/skills/` 内）の場合は、そのプラグインの
version（`.claude-plugin/plugin.json`、`plugin.json`、`.codex-plugin/plugin.json` の
3つで同じ値）の
bump が必要なことをユーザーに伝える。

### 5. 完了報告

計装（または除去・更新）したスキルとバージョンの一覧を報告する。
配置済み（実環境にコピー済み）のスキルを計装した場合は、`skill-packager` での
バージョンアップ反映を案内する。

## 除去（計装を外す）

「計装を外して」「observerを取り除いて」と言われた場合は、マーカー
`<!-- bitzskills-observer:start -->` から `<!-- bitzskills-observer:end -->`
までの行を削除し、Step 4（patch bump）と Step 5 を同様に行う。
マーカー外の本文には一切触れない。

## 注意

- 注入・除去はマーカー間の操作に限定し、対象スキル本来の内容を変更しない。
  本文の改善が必要だと気づいた場合は `skill-optimizer` を案内する
- 自己観察セクションを二重に注入しない（Step 2 の確認を省略しない）
- `skill-observer` 自身と `skill-improver` は計装しない（観察の再帰を避ける）
