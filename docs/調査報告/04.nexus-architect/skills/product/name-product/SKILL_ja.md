---
description: |
  プロダクトをアルファベットのアクロニム（頭字語）として命名します — すべての文字が英単語の頭文字である、短くて発音可能なラテン文字の名前であり、名前自体がプロダクトの価値を述べるフレーズに展開されます。ビジョン/価値観/ポジショニングに基づいており、候補を絞り込んで1つを推奨します。
  /product:name-product [target] [--input=<file|dir>] [--count=N] [--style=acronym|initialism|hybrid] [--seed=<letters|word>] [--auto] [--lang=ja|en]。
model: opus
user_invocable: true
---

# Product Naming (Acronym / Backronym)

## Desired Outcome

**ラテンアルファベットで綴られ**、その**すべての文字が英単語の最初の文字**に対応し、名前自体がプロダクトを説明するフレーズを兼ねるプロダクト名を作成します。以下を納品します：

- **プロダクト名（Product Name）** — `reports/00_core/product-name.md`
  - **ワードバンク（word bank）**: プロダクトのビジョン、価値観、差別化要因、ドメインから抽出された、頭文字ごとにグループ化された英語の候補単語群（各単語には、それが表現するテーマがタグ付けされています）
  - **候補名（Candidate names）**（デフォルトは 5）: それぞれが短く発音可能な文字列と、その**完全な展開（full expansion）** — 文字ごとに1つの英単語 — および、展開された内容が何を主張しているかを示す1行の読み書き
  - 命名基準（識別性がある、短い、発音可能である、適切である、展開可能である、保護可能である）に基づいて各候補を採点する**スクリーニング表（screening table）**
  - **3つのショートリスト**と、`VIS-` IDs にトレースされる根拠を伴う**1つの推奨名（recommended name）**
  - 未解決の質問（Open Questions）としてリストされた**利用可能性チェック（Availability checks）** — 決してクリアされたと断言しないこと
  - 各候補および推奨名は `NAM-` ID を持ちます

名前は飾りではありません。PR-FAQ の見出し、ポジショニングキャンバス、そしてすべての UI モックへと流れ込むため、それらの成果物が語るのと同じ価値の物語に耐えうるものでなければなりません。

## Invocation

```
/product:name-product [target] [--input=<file|dir>]... [--count=N] [--style=acronym|initialism|hybrid] [--seed=<letters|word>] [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `target` | Optional | 再命名するプロダクトのアイデア/仮称、またはシードとするテーマ |
| `--input=<file\|dir>` | Optional, repeatable | ブリーフ、ブランドノート、用語集、過去のドキュメント |
| `--count=N` | Optional | 生成する候補名の数（デフォルト 5） |
| `--style` | Optional | `acronym` = 単語として発音される（例: NEXUS）。`initialism` = 文字ごとに綴られる（例: SDK）。`hybrid`。デフォルトは `acronym` |
| `--seed=<letters\|word>` | Optional | 文字を固定するか、与えられたベース単語をバクロニム（backronym）化します（例: `--seed=SCALAR` は文字ごとに単語を見つけます） |
| `--auto` | Optional | ファシリテーションをスキップします。入力のみから生成します。不明点は `TBD` になります |
| `--lang` | Optional | 出力言語を上書きします |

## Decision Criteria

- **制約は絶対的です**: 最終的な名前のすべての文字は、正確に1つの英単語にマッピングされなければならず、文字ごとの単語は全体としてプロダクトに関する首尾一貫したフレーズとして読めなければなりません。展開が破綻している、強引である、または無意味な候補は、どれほど響きが良くても却下します。
- **発音可能で短い**（`acronym` スタイルの場合）: 4〜6 文字、≤3 音節、1つの明白な読み方を目指します。`initialism` スタイルはより短く（2〜4 文字）てもよいですが、展開可能でなければなりません。
- **適切であり、一般的ではない**: 展開はカテゴリの自明の理（「Fast Reliable Efficient System」はすべてを説明している → 却下）ではなく、*この*プロダクトの差別化を説明するものでなければなりません。
- **根拠があり、決してでっち上げない**: 展開に使用する単語は、プロダクト自身のビジョン/価値観/ポジショニングの語彙から取得します。名前、ドメイン、商標が利用可能であると主張**しない**でください — 利用可能性は外部で検証され、未解決の質問（Open Questions）に記録されます。
- **終了条件（Stop condition）**: 有効な完全展開とスクリーニングスコアを持つ `--count` 個の候補が存在すること。3つのショートリストと、根拠を伴う1つの推奨事項が書かれていること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/00_core/vision-mission-value.md` | Recommended | `/product:define-vision` | ビジョン/価値観をインラインで引き出すか、`TBD` とします |
| `reports/01_ux/positioning.md` | Optional | `/product:design-positioning` | 進行します。ビジョンの語彙のみを使用します |
| `reports/01_ux/personas.md` | Optional | `/product:generate-persona` | トーンの手がかりなしで進めます |
| `reports/00_core/scope-definition.md` | Optional | `/product:define-scope` | 進行します |
| `work/pipeline-progress.json` | Recommended | `/product:init-output` | `output_language` を尋ねます |

## Process

1. **コンテキストの読み取り** — `--input`、ビジョン/価値観、ポジショニング、ペルソナ、スコープ、および `work/traceability.json` をロードします。荷重を支える価値のキーワードと差別化要因を抽出し、それぞれに `VIS-`/`POS-` ソースを付けます。
2. **引き出し（Elicit）（ギャップ駆動、`--auto` の場合はスキップ）** — トーン（技術的 vs 親しみやすい）、含めたい/避けたい文字/単語、および名前の言語（`--lang=ja` の場合でも名前はラテンアルファベットのままです）を確認します。
3. **ワードバンクの構築（Build the word bank）** — テーマキーワードごとに強力な英単語をリストアップし、各単語の頭文字とそれが表現するテーマを記録します。これが展開の原材料となります。
4. **候補の生成（Generate candidates）** — `@rules/product/naming-frameworks.md` を適用します。両方向から機能させます: フォワード（価値のある単語の頭文字を組み合わせて発音可能な文字列にする）およびバックワード（発音可能な文字列を選び、バンクから1文字につき1つの英単語を当てはめる）。`--seed` を尊重します。**完全な文字ごとの展開**を持つ `--count` 個の候補を作成します。
5. **スクリーニング（Screen）** — 6つの命名基準で各候補を採点します。強引な、または一般的な展開のものは除外します。発音と音節数に注意してください。
6. **利用可能性（Availability）** — 実行すべき正確なチェック（商標クラス、`.com`/ドメイン、アプリストア、ワードバンク自身の競合他社との衝突）を**未解決の質問（Open Questions）**としてリストアップします。決してクリアしたとマークしないでください。
7. **ショートリストと推奨（Shortlist & recommend）** — 3つを選び、次に1つを選びます。展開が満たす `VIS-` ID を引用して根拠とします。`NAM-` ID を割り当てます。
8. **トレーサビリティの追記** — 各 `NAM-` ノードについて、`{id, type:"name", title, skill:"name-product", source_file, upstream:[VIS-…, POS-…]}` を `work/traceability.json` に追加します。
9. **記録** — `reports/00_core/product-name.md` を書き込みます。推奨事項を `work/context.md` に追記します。利用可能性のチェックとすべての `TBD` を未解決の質問（Open Questions）にログとして記録します。

## Output

`reports/00_core/product-name.md` — ワードバンク、完全な展開を伴う候補テーブル、スクリーニングスコア、ショートリスト、1つの推奨名、Upstream 列を持つ `NAM-` ID テーブル、および利用可能性のための未解決の質問（Open Questions）ブロックが含まれます。`output_language` に関係なく、名前の文字列自体は常にラテンアルファベットです。周囲の文章は設定された言語に従います。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/naming-frameworks.md` | アクロニム/バクロニムの構築 + 命名品質基準 |
| `@rules/product/vision-frameworks.md` | 展開が表現しなければならない価値の語彙のソース |

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:define-vision` | Upstream — 展開がエンコードするビジョン/価値観を提供します |
| `/product:design-positioning` | Upstream (soft) — 差別化の語彙。選択された名前を消費します |
| `/product:generate-ui-mock` | Downstream — 名前はすべてのモックに表示されます |
| `/product:adapt-change` | ビジョンまたはポジショニングが変わったときにこの Skill を再実行します |
