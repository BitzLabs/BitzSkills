# BitzSkills — エージェントスキル開発ライブラリ

`~/Dev/BitzSkills` は、[Agent Skills](https://agentskills.io/specification)
オープン標準に準拠したスキルの**ライブラリ（保管庫）**です。
スキルの「作成 → 検証 → テスト → 評価 → 最適化 → 配置」の全工程を、
機能毎に分割した7つの専門スキルでカバーします。

リポジトリは**モノレポ**構成で、ルートがマーケットプレイス `bitzskills`、
`plugins/` 配下の各フォルダが1つのプラグインです。第1号のプラグイン
`skill-creator` に上記7スキルが含まれ、Claude Code と Google Antigravity 2.0 の
両方に一括インストールできます（後述「プラグインとしてのインストール」）。

> **重要**: `plugins/*/skills/` に置いただけではどのエージェントにも認識されません。
> 実際に使うにはプラグインとしてインストールするか、`skill-packager` で
> 各プラットフォームのパスへ個別にインストールします。

## ディレクトリ構成

```
BitzSkills/
├── CLAUDE.md                   # リポジトリの規約（Claude Code向けガイド）
├── .claude-plugin/
│   └── marketplace.json        # マーケットプレイス定義（全プラグインを列挙）
├── plugins/
│   └── skill-creator/          # プラグイン第1号: スキル開発ツール群
│       ├── .claude-plugin/
│       │   └── plugin.json     # Claude Code プラグインマニフェスト
│       ├── plugin.json         # Antigravity 2.0 プラグインマニフェスト
│       └── skills/             # プラグインに含まれるスキル
│           ├── skill-creator/      # 新規スキルの設計・雛形作成
│           ├── skill-validator/    # 仕様準拠チェック（lint）
│           ├── skill-optimizer/    # 既存スキルの最適化
│           ├── skill-tester/       # テストケース設計と実行
│           ├── skill-evaluator/    # 実行結果の採点・レポート
│           ├── skill-packager/     # インストール・更新・削除・配布
│           └── skill-pipeline/     # 全工程を案内する統括スキル
└── evals/                      # テスト成果物（スキルフォルダの外・全プラグイン共用）
    └── <skill-name>/
        ├── cases.md            # テストケース定義
        ├── runs/<n>/           # 実行ログ・生成物
        └── report.md           # 評価レポート
```

各スキルは `SKILL.md`（frontmatter + 指示本文）と、必要に応じて
`references/`（詳細ドキュメント）を持ちます。スキルは**自己完結**しており、
フォルダ単位でコピーしても壊れません（スキル間の連携は名前の言及のみ）。

---

## 7つのスキル

### skill-creator — 新規スキルの作成

新しいスキルを対話的に設計し、仕様に合った雛形を作成します。

- **いつ使う**: 「新しいスキルを作りたい」「SKILL.mdを作成したい」
- **やること**: ヒアリング（スキル名・トリガー・単一責務か・複雑度）→
  `skills/<name>/` の作成 → frontmatter（name / description / metadata）と
  本文の記述 → validator / tester での次工程を提案
- **リファレンス**: `references/spec.md` — frontmatter仕様・metadata運用規約・
  progressive disclosure の正式な定義（**このライブラリの仕様の「正」**）

### skill-validator — 仕様準拠チェック

スキルが仕様に準拠しているかを検査し、✅/❌/⚠️ のチェックリストで報告します。
修正は行いません（修正は optimizer の担当）。

- **いつ使う**: 「スキルを検証して」「仕様に合っているか確認して」、
  creator での作成直後
- **検査項目**（`references/checklist.md` に正式な一覧）:
  - A: 構造（SKILL.mdの存在、frontmatterがYAMLとしてパース可能か）
  - B: name（命名規則、フォルダ名との一致）
  - C: description（1024文字以内、「何を/いつ」の両方があるか）
  - D: 本文（500行未満、相対パス参照の実在）
  - E: 設計品質（単一責務・冗長性・安全確認 — ⚠️判定のみ）
  - F: metadata（semver形式のversion、author、日付、installed-*の混入禁止）

### skill-optimizer — 既存スキルの最適化

既存スキルの品質を4観点で改善し、変更に応じてバージョンを bump します。

- **いつ使う**: 「スキルを改善して」「descriptionを最適化して」
  「スキルがうまく発動しない」、validator / evaluator で問題が出たとき
- **4観点**: (a) description最適化（発動精度向上、改善前後を提示して承諾を得る）
  (b) progressive disclosure（長い本文を references/ へ分離）
  (c) トークン効率（冗長表現の圧縮） (d) 構造改善（decision tree 導入）
- **バージョンbump**: 変更適用時に `metadata.version` を自動で上げ、
  `updated` を更新（判定基準は `references/optimization-guide.md`）

### skill-tester — テストケース設計と実行

対象スキルからテストケースを設計し、「スキルあり」と「スキルなしベースライン」の
両方で実行して結果を `evals/` に保存します。

- **いつ使う**: 「スキルをテストして」「このスキルが効いているか確かめたい」
- **ケースの3種別**: 正常系（典型トリガー）／エッジケース（情報不足・境界値）／
  発動判定（descriptionだけで使う/使わないを判別できるか）
- **成果物**: `evals/<skill-name>/cases.md`（入力プロンプト＋アサーション）と
  `runs/<n>/`（log.md＋生成物）。書式は `references/test-design.md` で定義

### skill-evaluator — 結果の採点とレポート

tester の実行結果をアサーションに照らして採点し、`report.md` を作成します。

- **いつ使う**: 「テスト結果を評価して」「スキルの効果を測って」、tester の実行後
- **採点原則**（`references/grading-rubric.md`）: 証拠主義（根拠を示せない判定は
  「判定不能」）、アサーションの文言に忠実、過学習の警告（特定ケースを通すだけの
  改善提案はしない）
- **レポート内容**: 合格率サマリー、ケース毎の合否と根拠、スキルあり/なしの
  比較所見、優先度付き改善提案

### skill-packager — パッケージ管理

ライブラリと実環境の間のライフサイクル（インストール・バージョンアップ・
アンインストール・配布）を管理します。

- **いつ使う**: 「スキルをインストールして」「アップデートして」
  「アンインストールして」「配布用にまとめて」
- **操作一覧**:

| 操作 | 内容 |
| --- | --- |
| インストール | 配置先へコピーし、frontmatterに `installed-at` / `installed-from` を追記（stamp）。シンボリックリンク配置も選択可（開発中向け・stampなし） |
| バージョンアップ | 配置先とライブラリの `metadata.version` を semver 比較し、変更点を提示 → 承諾 → 入れ替え＋再stamp |
| アンインストール | `installed-from` で出自を確認 → 承諾を得て配置先のみ削除（ライブラリは無傷） |
| 配布 | スキルフォルダを zip 化（`zip -r` または `python3 -m zipfile -c`） |
| 棚卸し | 配置先の frontmatter を読んで name / version / installed-at / installed-from を一覧化 |

- **リファレンス**: `references/lifecycle.md`（stamp手順・semver比較・上書き
  安全判定）、`references/platform-paths.md`（プラットフォーム別配置パス）

### skill-pipeline — 統括（オーケストレーター）

全工程を順に案内します。自身は作業せず、各専門スキルへ委譲します。

- **いつ使う**: 「スキルを作って公開まで面倒を見てほしい」
  「スキル開発の進め方が分からない」
- **標準フロー**:

```
skill-creator（作成）
  → skill-validator（検証）…… ❌があれば optimizer で修正して再検証
  → skill-tester（テスト）
  → skill-evaluator（評価）
      → 不合格: optimizer → validator → tester → evaluator を反復
      → 合格:   optimizer で description 最終調整 → skill-packager（配置）
```

---

## metadata 運用規約（バージョン管理）

全スキルの frontmatter に以下を必須で持たせます（正式な定義は
`plugins/skill-creator/skills/skill-creator/references/spec.md`）。

```yaml
---
name: pdf-processing
description: 何をするか＋いつ使うか。
metadata:
  version: "0.1.0"      # semver。新規作成時は 0.1.0
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-05" # 内容を変更したら必ず更新
---
```

### bump 規則

| bump | 対象となる変更 |
| --- | --- |
| patch (0.1.0→0.1.1) | 挙動を変えない修正（誤字・表現の圧縮） |
| minor (0.1.0→0.2.0) | 責務の範囲内での改善（手順追加・description改善・references追加） |
| major (0.1.0→1.0.0) | 互換性を壊す変更（責務・トリガー・成果物形式の変更） |

### インストール状態の自己記述

コピー配置時、packager が**配置先のみ**に以下を追記します
（ライブラリ側に書くのは禁止。validator の F4 が検出します）。

```yaml
  installed-at: "2026-07-05"
  installed-from: /home/hide/Dev/BitzSkills
```

台帳ファイルは使わず、配置先の SKILL.md 自身が「どこから・いつ・どの
バージョンが入ったか」を記述します。

---

## プラグインとしてのインストール（推奨）

`plugins/skill-creator/` がプラグインになっており、7スキルを一括導入できます。

### Claude Code

```bash
# 開発中の動作確認（インストール不要。プラグインのフォルダを指す）
claude --plugin-dir ~/Dev/BitzSkills/plugins/skill-creator
```

```
# マーケットプレイス登録してインストール（Claude Code 内で実行）
/plugin marketplace add ~/Dev/BitzSkills
/plugin install skill-creator@bitzskills
```

GitHub に公開した後は `/plugin marketplace add <owner>/BitzSkills` でも登録できます。
スキル名は `skill-creator:skill-validator` のようにプラグイン名で名前空間化されます。

### Google Antigravity 2.0

```bash
agy plugin install ~/Dev/BitzSkills/plugins/skill-creator   # プラグインのフォルダを指定
agy plugin list                                             # 確認
```

プラグインは `~/.gemini/config/plugins/skill-creator/` にステージされます。
`agy plugin install` が使えない環境では、下記の個別配置にフォールバックします。

## プラットフォーム別配置パス（個別インストール）

| プラットフォーム | ワークスペース | グローバル |
| --- | --- | --- |
| Claude Code | `<workspace>/.claude/skills/` | `~/.claude/skills/` |
| Google Antigravity | `<workspace>/.agents/skills/` | `~/.gemini/config/skills/` |

- **コピー**: 配置先が自己完結。更新は packager のバージョンアップ操作で行う
- **シンボリックリンク**: ライブラリの更新が即反映。開発中のスキル向け
- プラグイン経由の導入分には `installed-at` / `installed-from` の stamp は付きません
  （プラットフォーム側がバージョン管理するため）

---

## 使い方の例

エージェント（Claude Code / Antigravity）に BitzSkills のスキル群を
インストールした状態で、次のように話しかけます。

| やりたいこと | 話しかけ方の例 |
| --- | --- |
| 新しいスキルを一から仕上げたい | 「スキルを作って公開まで面倒を見てほしい」（→ pipeline） |
| スキルの雛形だけ作りたい | 「PDFを処理する新しいスキルを作りたい」（→ creator） |
| 既存スキルをチェックしたい | 「skills/foo を検証して」（→ validator） |
| 発動精度を上げたい | 「foo のdescriptionを最適化して」（→ optimizer） |
| 効果を測りたい | 「foo をテストして」→「結果を評価して」（→ tester → evaluator） |
| 実環境で使いたい | 「foo をClaude Codeにインストールして」（→ packager） |
| 更新を反映したい | 「foo をアップデートして」（→ packager） |
| 使うのをやめたい | 「foo をアンインストールして」（→ packager） |

### 開発時の規約（このリポジトリを編集するとき）

- スキルを追加・変更したら validator のチェックリストで検証する
- 変更したら version を bump し `updated` を更新する
- テスト成果物はスキルフォルダ内ではなく `evals/<skill-name>/` に置く
- 他スキルの `references/` を相対パスで参照しない（連携は名前の言及のみ）
