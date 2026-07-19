---
name: ddd-doctor
description: bitz-ddd の実行環境を診断する読み取り専用スキル。依存プラグイン bitz-sdd の有効性・semver 制約充足と、利用プロジェクトの .spec/design/ ワークスペース前提を検査し、欠如・不満足時は導入手順つき修正案を報告する。「ddd-doctor」「bitz-ddd の診断」「環境診断」「DDD 環境の健全性チェック」「依存関係を確認して」と言われたとき、または ddd-story / ddd-model / ddd-evaluate を使う前後に環境の健全性を確認したいときに使用する。
metadata:
  version: "1.0.0"
  author: br7.hide
  created: "2026-07-19"
  updated: "2026-07-19"
---

# DDD Doctor — bitz-ddd 環境診断

## 前提: 読み取り専用

本スキルは**読み取り専用**です。対象プロジェクト・配置先のいかなるファイルへの
書き込みも行いません（診断と修正案の提示のみ。修正の実施はユーザー自身が行います）。

## 目的

bitz-ddd（ddd-story / ddd-model / ddd-evaluate）は bitz-sdd プラグインとの併用を前提に
成果物を `.spec/design/` へ書き込みます。しかし bitz-sdd が未導入・バージョン不足、
あるいは `.spec/` ワークスペース自体が存在しない状態で bitz-ddd の各スキルを実行すると、
成果物の書き込み先が無い、または bitz-sdd 側の規律（frontmatter 契約・ID 体系）と
噛み合わない事故が起きます。本スキルはその前提条件を実行前に検査します。

## 診断項目

### (a) 依存プラグイン bitz-sdd の有効性・semver 制約充足

bitz-ddd の3マニフェスト（`.claude-plugin/plugin.json` / `plugin.json` /
`.codex-plugin/plugin.json`）は `metadata.dependencies: ["bitz-sdd>=2.0"]` を宣言しています。

| 検査 | 方法 |
| --- | --- |
| bitz-sdd プラグインが導入・有効化されているか | インストール済みプラグイン一覧（取得可能な場合。例: `installed_plugins.json` やプラットフォームのプラグイン一覧コマンド）を確認 |
| 導入済み bitz-sdd の version が `>=2.0` を満たすか | 導入済みマニフェストの `version` を semver 比較 |

- **欠如**（bitz-sdd が見当たらない）の場合: **FAIL** とし、導入手順を含む修正案を報告する。
  例: `/plugin marketplace add <このリポジトリ>` → `/plugin install bitz-sdd@bitzskills`
  （Antigravity 2.0 なら `agy plugin install <リポジトリ>/plugins/bitz-sdd`、
  Codex CLI なら `codex plugin add bitz-sdd@bitzskills`）
- **制約不満足**（導入済みだが version が `>=2.0` 未満）の場合: **FAIL** とし、
  アップデート手順（プラットフォームのプラグイン更新コマンド）を修正案として報告する
- 確認手段が利用できず有効性を確定できない場合は **WARN** とし、「確認不能である」旨と
  本体環境での再確認を促す文言を診断結果に明記する

### (b) `.spec/design/` 配置前提の診断

利用プロジェクトに `.spec/design/` が存在する場合、bitz-ddd の成果物
（`domain-model.md` / `stories/` 配下のファイル）はそこへ書き込まれる前提です。

| 検査 | 方法 |
| --- | --- |
| `.spec/` ワークスペース自体が存在するか | 対象プロジェクト直下（または各サブワークスペース）の `.spec/` を確認 |
| `.spec/design/` が存在するか | `.spec/` 配下の `design/` を確認 |
| 既存の `domain-model.md` / `stories/` と bitz-sdd の frontmatter 契約
  （sdd-core の artifact-frontmatter 書式）に矛盾がないか | 既存ファイルがあれば frontmatter の ID 体系（`DSN-NNN`）等を確認 |

- `.spec/design/` が無い（`.spec/` 自体が無い、または `design/` サブディレクトリが無い）場合は
  **WARN** とし、「bitz-ddd の成果物配置前提となる `.spec/design/` ワークスペースが存在しない」旨と、
  bitz-sdd 側での作成手順（例: `sdd-design` スキルの初期化、または `scripts/spec scaffold` 等）を
  修正案として報告する
- `.spec/design/` が存在し矛盾も無ければ **PASS**

### (c) 全て OK の場合

全診断項目が PASS の場合は OK 判定を下し、各項目の根拠（何を確認して PASS と判断したか）を
簡潔に報告します。

## 出力形式

チェックリスト形式で報告する:

```
# ddd-doctor 診断結果

## (a) bitz-sdd 依存
- [PASS] bitz-sdd 2.0.0 が導入済み（制約 >=2.0 を満たす）

## (b) .spec/design/ 配置前提
- [PASS] .spec/design/ が存在する

## 総合: OK — bitz-ddd の各スキルを利用できます
```

不合格時の例:

```
## (a) bitz-sdd 依存
- [FAIL] bitz-sdd が見当たらない
  → 修正案: `/plugin marketplace add <このリポジトリ>` の後
    `/plugin install bitz-sdd@bitzskills` を実行してください

## (b) .spec/design/ 配置前提
- [WARN] .spec/design/ が存在しない
  → 修正案: bitz-sdd の sdd-design スキルで設計工程を開始するか、
    `scripts/spec scaffold` で .spec/ ワークスペースを初期化してください

## 総合: 1 FAIL / 1 WARN — 修正を実施しますか？
```

## してはいけないこと

- 対象プロジェクト・配置先への書き込み（本スキルは診断と修正案の提示のみを行う）
- ユーザー承認なしの修正実施（bitz-sdd の導入・`.spec/` の作成はユーザー自身が行う）
- 確認不能な項目を確認済みであるかのように断定して報告すること
