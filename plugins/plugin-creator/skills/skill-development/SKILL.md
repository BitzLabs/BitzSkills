---
name: skill-development
description: Claude Code / Antigravity 2.0 プラグインに同梱するスキル（SKILL.md）の作成・改善を支援する。「プラグインにスキルを追加したい」「スキルを書きたい」「descriptionを改善したい」「スキルの構成を整理したい」と言われたときや、progressive disclosure・トリガー設計・スキル記述スタイルの指針が必要なときに使用する。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-06"
---

# skill-development

## 目的

プラグインに同梱する効果的なスキルを作成するための指針を提供する。

スキルとは、専門知識・ワークフロー・ツールを提供してエージェントの能力を拡張する
自己完結型パッケージである。特定ドメインの「オンボーディングガイド」として、
汎用エージェントを手続き的知識を備えた専門エージェントに変える。

SKILL.md の形式（frontmatter の name / description、progressive disclosure、
`scripts/` `references/` `examples/` の同梱）は Agent Skills 標準として
**Claude Code と Antigravity 2.0 で共通**。スキルは最もポータブルな
コンポーネントであり、両対応プラグインの中核はスキルで作るのが原則。

**注**: スキル開発の全工程（作成→検証→テスト→評価→最適化→配置）を体系的に
進めたい場合は、`skill-creator` プラグインのスキル群（skill-creator /
skill-validator / skill-tester / skill-evaluator / skill-optimizer /
skill-packager / skill-pipeline）が使える。本スキルは「プラグインに同梱する
スキル」に固有の観点を扱う。

## スキルの構造

```
skill-name/
├── SKILL.md（必須）
│   ├── YAML frontmatter（name / description 必須）
│   └── マークダウン本文（指示）
└── バンドルリソース（任意）
    ├── scripts/     # 実行コード（Python/Bash等）
    ├── references/  # 必要時にコンテキストへ読み込むドキュメント
    ├── examples/    # コピーして使える実例
    └── assets/      # 出力に使うファイル（テンプレート・画像等）
```

### リソースの使い分け

| フォルダ | 入れるもの | 判断基準 |
| --- | --- | --- |
| `scripts/` | 検証ツール・テストヘルパー・自動化スクリプト | 同じコードを毎回書き直している、決定的な動作が必要 |
| `references/` | 詳細パターン・API仕様・スキーマ・ドメイン知識 | 作業中に参照すべき文書。SKILL.mdを痩せさせるために分離 |
| `examples/` | 完全に動くスクリプト・設定ファイル・テンプレート | そのままコピーして使える実例 |
| `assets/` | ロゴ・テンプレート・ボイラープレート | コンテキストに読み込まず、成果物に使うファイル |

**重複を避ける**: 情報は SKILL.md か references のどちらか一方に置く。
SKILL.md には本質的な手順とワークフローの指針だけを残し、詳細なリファレンス・
スキーマ・長い例は references に移す。

## Progressive Disclosure（段階的開示）

スキルは3段階の読み込みでコンテキストを節約する:

1. **メタデータ（name + description）** — 常にコンテキストにある（~100語）
2. **SKILL.md 本文** — スキルがトリガーされたとき（5000語未満）
3. **バンドルリソース** — 必要になったときだけ（スクリプトは読まずに実行可能）

## スキル作成プロセス

### Step 1: 具体例でスキルを理解する

効果的なスキルを作るには、そのスキルがどう使われるかの具体例を明確にする。
「このスキルはどんな機能を持つべきか」「ユーザーが何と言ったらトリガーすべきか」
を確認する。一度に質問しすぎず、重要な質問から順に聞く。

### Step 2: 再利用可能なコンテンツを設計する

各具体例について「ゼロから実行するとどうなるか」を考え、繰り返し必要になる
scripts / references / assets を洗い出す。

- PDF回転を毎回コードで書く → `scripts/rotate_pdf.py` を同梱
- Webアプリの雛形を毎回書く → `assets/hello-world/` テンプレートを同梱
- テーブルスキーマを毎回調べ直す → `references/schema.md` を同梱
- hooks.json の検証を毎回行う → `scripts/validate-hook-schema.sh` を同梱

### Step 3: 構造を作る

```bash
mkdir -p plugin-name/skills/skill-name/{references,examples,scripts}
touch plugin-name/skills/skill-name/SKILL.md
```

実際に使うフォルダだけ作成する。

### Step 4: スキルを書く

スキルは「別のエージェントインスタンスが使うもの」として書く。
エージェントにとって有益かつ自明でない情報（手続き的知識・ドメイン固有の詳細・
再利用可能な資産）に集中する。

**記述スタイル**: 本文全体を**命令形**（動詞から始まる指示）で書く。
二人称は使わない。

- ✅ 「フックを作るには、イベント種別を定義する」
- ❌ 「あなたはイベント種別を定義する必要があります」

**description（frontmatter）**: 第三者視点で、具体的なトリガーフレーズを含める。

- ✅ 「『フックを作りたい』『PreToolUseフックを追加』と言われたとき、
  またはフックイベントに言及されたときに使用する」
- ❌ 「フック関連の作業で使う」（曖昧・トリガーなし）

**SKILL.md 本文で答えるべき問い**:

1. スキルの目的は何か（数文で）
2. いつ使うべきか（frontmatter の description にトリガー付きで）
3. 実際にどう使うか（作成した全リソースへの参照を含める）

**本文はリーンに保つ**: 目安1500〜2000語。詳細は references へ:

```markdown
## 追加リソース

### リファレンス
- **`references/patterns.md`** — よくあるパターン集
- **`references/advanced.md`** — 発展的な使い方

### 実例
- **`examples/example-script.sh`** — 動作する実例
```

### Step 5: 検証・テスト

1. **構造**: `plugin-name/skills/skill-name/SKILL.md` が存在するか
2. **frontmatter**: name / description があるか
3. **トリガー**: description に具体的なユーザー発話が含まれるか
4. **スタイル**: 本文が命令形か
5. **progressive disclosure**: SKILL.md がリーンで、詳細が references にあるか
6. **参照整合性**: 参照先ファイルが実在するか
7. **実例・スクリプト**: 完全で実行可能か

`skill-reviewer` エージェント（本プラグイン同梱）にレビューを依頼できる。
より体系的な検証には `skill-creator` プラグインの `skill-validator` が使える。

ローカルでのトリガーテスト:

```bash
# Claude Code
claude --plugin-dir /path/to/plugin
# スキルがトリガーされるはずの質問をして、読み込まれるか確認する

# Antigravity 2.0
agy plugin install /path/to/plugin && agy
# 確認後は agy plugin uninstall <name> で戻せる
```

### Step 6: 反復改善

実タスクでスキルを使い、つまずきや非効率に気づいたら SKILL.md やリソースを
更新する。よくある改善: トリガーフレーズの強化、長いセクションの references
への移動、実例・スクリプトの追加、曖昧な指示の明確化。

## プラグイン固有の考慮事項

- **配置場所**: プラグインの `skills/` フォルダ内にスキルごとのサブフォルダ
- **自動発見**: `SKILL.md` を含むサブフォルダが自動で読み込まれる
- **パッケージ不要**: プラグインの一部として配布されるので、スキル単体の
  zip 化は不要（単体配布したい場合は `skill-packager` スキルが使える）

## よくある失敗

1. **弱いトリガー**: 「フックのガイダンスを提供する」のような曖昧な description
   → 具体的なフレーズを列挙する
2. **SKILL.md の肥大化**: 8000語を1ファイルに詰め込む
   → 1500〜2000語に絞り、詳細を references へ
3. **二人称の文体**: 「あなたは〜すべきです」
   → 命令形「〜する」に統一
4. **リソース参照漏れ**: references/ があるのに SKILL.md から言及していない
   → 「追加リソース」セクションで必ず列挙する

## 追加リソース

- **`references/skill-creator-methodology.md`** — スキル設計方法論の詳細
  （具体例駆動の設計・リソース分割の判断基準・検証チェックリスト）
