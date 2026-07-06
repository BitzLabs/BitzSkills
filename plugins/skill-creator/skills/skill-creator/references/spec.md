# Agent Skills 仕様リファレンス

`skill-creator` がスキルを作成する際に従う仕様の詳細。
[Agent Skills](https://agentskills.io/specification) というオープン標準に基づく。
Claude Code、Google Antigravityなど複数のエージェント製品がこの標準に準拠しており、
ここでは標準部分のみを扱う（製品固有の配置パスは `skill-packager` の担当）。

## ディレクトリ構成

```
skill-name/
├── SKILL.md          # 必須: メタデータ(frontmatter) + 本文の指示
├── scripts/           # 任意: 実行コード（Python/Bash等）
├── references/        # 任意: 詳細ドキュメント
├── assets/            # 任意: テンプレート・画像・データファイル
└── ...                # その他任意のファイル・ディレクトリ
```

`SKILL.md` だけが必須。それ以外は必要なときだけ追加する。

## frontmatterフィールド

| フィールド | 必須 | 制約 |
| --- | --- | --- |
| `name` | 必須（実装によっては省略時にフォルダ名がデフォルト） | 1〜64文字。英小文字・数字・ハイフンのみ。先頭/末尾ハイフン禁止。連続ハイフン(`--`)禁止。**親フォルダ名と一致させる**（他ツールとの互換性のため、常に明示するのが望ましい） |
| `description` | 必須 | 1〜1024文字。何をするか＋いつ使うかを明記する。第三者視点・具体的なキーワードを含めると良い |
| `license` | 任意 | ライセンス名、またはバンドルしたライセンスファイルへの参照 |
| `compatibility` | 任意 | 最大500文字。対象製品や必要な環境（システムパッケージ・ネットワークアクセス等）を記載。ほとんどのスキルには不要 |
| `metadata` | 任意 | 任意のkey-valueマップ。author/versionなど、仕様に定義されていない付加情報を格納 |
| `allowed-tools` | 任意・実験的 | 事前承認するツールをスペース区切りで指定（例: `Bash(git:*) Read`）。対応状況は実装依存（Claude Code は対応。Antigravity 2.0 の仕様には存在せず、無視される） |

### 最小構成の例

```yaml
---
name: skill-name
description: このスキルが何をするか、いつ使うかの説明。
---
```

### オプションフィールドを使う例

```yaml
---
name: pdf-processing
description: PDFのテキスト抽出・フォーム入力・結合を行う。PDFやフォーム、文書抽出に関する作業のときに使う。
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---
```

## metadata運用規約（このライブラリの規約）

オープン標準では `metadata` は任意のkey-valueマップだが、このライブラリでは
ライフサイクル管理（インストール・バージョンアップ・アンインストール）のために
以下のフィールドを**必須**とする。

| フィールド | 形式 | 内容 |
| --- | --- | --- |
| `metadata.version` | semver文字列（`"X.Y.Z"`、必ず引用符付き） | スキルのバージョン。新規作成時は `"0.1.0"` |
| `metadata.author` | 文字列 | 作成者 |
| `metadata.created` | `"YYYY-MM-DD"` | 作成日 |
| `metadata.updated` | `"YYYY-MM-DD"` | 最終更新日。内容を変更したら必ず更新する |

### 記入例

```yaml
---
name: pdf-processing
description: PDFのテキスト抽出・フォーム入力・結合を行う。PDFやフォーム、文書抽出に関する作業のときに使う。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-05"
---
```

### バージョンbump規則

スキルの内容を変更したら、変更と同じコミット単位で `version` を上げ、
`updated` を当日日付にする。

| bump | 対象となる変更 |
| --- | --- |
| **patch** (0.1.0→0.1.1) | 挙動を変えない修正: 誤字・表現の圧縮・references内の説明補強 |
| **minor** (0.1.0→0.2.0) | 責務の範囲内での挙動追加・改善: 手順の追加、descriptionの改善、referencesファイルの追加 |
| **major** (0.1.0→1.0.0) | 互換性を壊す変更: 責務・トリガー条件の変更、成果物の形式変更、ワークフローの作り直し |

### インストール時フィールド（packagerが付与）

以下はライブラリ側のSKILL.mdには**書かない**。`skill-packager` がコピー配置時に
配置先のfrontmatterへ追記する（詳細はskill-packagerのlifecycle.md）。

| フィールド | 内容 |
| --- | --- |
| `metadata.installed-at` | インストール日（`"YYYY-MM-DD"`） |
| `metadata.installed-from` | インストール元ライブラリの絶対パス |

## エージェントがスキルを使う流れ（progressive disclosure）

1. **Discovery（発見）** — 会話開始時、エージェントは全スキルの `name` と
   `description` のみを読み込む（1スキルあたり目安 ~100トークン）
2. **Activation（活性化）** — タスクに関連しそうなら、そのスキルの
   `SKILL.md` 本文全体を読み込む（本文は500行/5000トークン未満を推奨）
3. **Execution（実行）** — `scripts/` `references/` `assets/` は、
   実際に必要になったときだけ読み込む

この段階的な読み込みを活かすため、SKILL.md本文は簡潔に保ち、詳細な内容は
`references/` 配下のファイルに分割する。ファイル参照はSKILL.mdからの相対パスで、
できるだけ1階層以内にとどめる。

## ベストプラクティス

- **単一責務**: 1スキル1目的。複数の目的がある場合はスキルを分割する。
- **明確なdescription**: エージェントがスキルを使うかどうかを判断する唯一の
  材料なので、何をするか・いつ使うかを具体的に書く。
- **スクリプトはブラックボックスとして扱わせる**: `scripts/` にコードを置く場合、
  エージェントにはソース全体を読ませず、まず `--help` 等を実行させてコンテキストを
  節約する。
- **複雑なスキルには判断分岐を入れる**: 状況によって取るべきアプローチが
  変わる場合は、本文に決定木（decision tree）的なセクションを設ける。

## プラットフォーム別配置

作成したスキルを実際のエージェント環境で有効化する手順（配置パスの正式な表、
コピー/シンボリックリンクの使い分け）は `skill-packager` スキルが担当する。
このリポジトリはスキルの「ライブラリ」であり、`skills/` に置くだけでは
どのエージェントにも認識されない点に注意。

## 出典

- [Agent Skills - Specification](https://agentskills.io/specification)
- [anthropics/skills - skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
