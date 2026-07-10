---
description: |
  デザインシステムを構築または組み込みます — DTCG の Design Tokens（デザイントークン）（カラー/タイポグラフィ/スペーシング/角丸/エレベーション）、コンポーネントのインベントリ、および使用ガイドライン — 再利用、バージョン管理、スワップができるように、単一のパイプライン実行とは別に管理されます。ポジショニング/ペルソナから構築するか、既存のシステム（Tailwind / DTCG / Figma Tokens / CSS テーマ）を --import します。lo または mid フィデリティで generate-ui-mock に供給されます。
  /product:design-system [--name=<id>] [--import=<path>] [--fidelity=lo|mid] [--auto] [--lang=ja|en]。
model: opus
user_invocable: true
---

# Design System

## Desired Outcome

`design-system/{name}/` の下に個別に管理される1つのデザインシステムを作成します：

1. **トークン（Tokens）** — `tokens.json`（W3C **DTCG** フォーマット）+ `tokens.css`（`:root` CSS 変数）: カラー、タイポグラフィ、スペーシング、角丸、エレベーション、モーション — 生のスケールとセマンティックなエイリアス（`color.bg/fg/primary/danger` など）。
2. **コンポーネント（Components）** — `components.md`（`CMP-` IDs）: バリアント/ステートと、**mid** フィデリティで使用されるトークンベースの CSS クラスを備えたコンポーネントインベントリ（Button, Input, Card, Modal など）。
3. **ガイドライン（Guidelines）** — `guidelines.md`: いつ何を使用するか、アクセシビリティのルール（コントラスト、ターゲットサイズ、視差効果の低減）、トーン＆マナー（voice & tone）。
4. **マニフェスト（Manifest）** — `manifest.json`: `name`、`version`（semver）、`mode`（`built`|`imported`）、`source`、`fidelity_support`、`generated_at`。
5. **プレビュー（Preview）** — `preview.html`: 視覚的なレビューのための自己完結型のトークン + コンポーネント ギャラリー。

これは、`generate-ui-mock` が消費する**「どのように見えるか」のレイヤー**です — ドメインストーリーが各画面が*何をするか*を決定し、デザインシステムが共有される*視覚的言語*を決定します。

## Invocation

```
/product:design-system [--name=<id>] [--import=<path>] [--fidelity=lo|mid] [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--name=<id>` | Optional | デザインシステムの名前（ケバブケース）。デフォルトは `default`。複数の名前付きシステムが共存できます。アクティブなものは progress ファイルに記録されます。 |
| `--import=<path>` | Optional | 既存のシステムを組み込みます：Tailwind 設定、DTCG JSON、Figma Tokens エクスポート、または CSS/SCSS 変数テーマ。**組み込み（incorporate）**モードに切り替わります。 |
| `--fidelity=lo\|mid` | Optional | システムがサポートしなければならないフィデリティ（`lo` = トークンのみ、`mid` = トークン + コンポーネントスタイル）。デフォルトは `lo`。モックがどちらかをレンダリングできるようにマニフェストに記録されます。 |
| `--auto` | Optional | ファシリテーションをスキップします。入力のみから導出/正規化します。 |
| `--lang` | Optional | 出力言語（ガイドライン/説明）を上書きします。 |

## Decision Criteria

- **トークンが基盤です。** すべてのもの（コンポーネント、モック）はトークンを参照し、決して生の値は参照しません — そうすることで、1つの信頼できる情報源（source of truth）が視覚的言語を統制し、自己完結型のモックが一貫性を保ちます。
- **構築（Build）vs 組み込み（incorporate）は明示的です。** `--import` → 既存のシステムを DTCG スキーマに正規化します。マッピングされていない値は `TBD` + 未解決の質問になります。`--import` なし → ブランドからトークンを導出します。
- **決してブランド価値をでっち上げないこと。** 組み込みモードでは、不明なものは推測ではなく `TBD` にマッピングされます。
- **アクセシビリティはゲートです（ビルドモード）。** 本文のコントラスト ≥ 4.5:1、大きなテキスト ≥ 3:1。色だけで意味を伝えないこと。視差効果の低減（reduced motion）を尊重します。チェックしたペアを記録します。
- **個別に管理される。** `reports/` の下ではなく、`design-system/{name}/` に書き込みます。変更時には `version` をバンプします。`options.design_system` をアクティブなシステムに向けます。この Skill は**スタンドアロン**です（フルパイプライン実行とは独立して、いつでも実行可能）。
- **終了条件（Stop condition）**: `tokens.json`（有効な DTCG）+ `tokens.css` + `components.md` + `guidelines.md` + `manifest.json` + `preview.html` が存在すること。progress ファイルがこのシステムを指していること。コントラストチェックが記録されているか（ビルドモード）、またはインポートのギャップが `TBD` としてリストアップされていること（組み込みモード）。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/01_ux/positioning.md` | Recommended (build) | `/product:design-positioning` | ニュートラルでアクセシブルなデフォルトパレットを導出します。ブランドの選択は `TBD` とマークします |
| `reports/01_ux/personas.md` | Recommended (build) | `/product:generate-persona` | デフォルトのアクセシビリティのベースライン（AA）を適用します |
| `reports/00_core/vision-mission-value.md` | Optional (build) | `/product:define-vision` | トーンはデフォルトでニュートラルになります |
| `--import` ターゲット | Required (incorporate) | User | 読み取れない/パースできない場合は、停止して報告します |

## Process

1. **モードの解決（Resolve mode）** — `--import` が存在 → 組み込み。それ以外 → 構築。`--name`（デフォルト `default`）と `--fidelity`（デフォルト `lo`）を解決します。
2. **構築モード（Build mode）** — ポジショニング（ブランド）、ペルソナ（a11y）、ビジョン（トーン）を読み取ります。基本の色相 + スケール、タイポグラフィスケール、スペーシングスケール（4/8 ベース）、角丸/エレベーションのステップを選択します。セマンティックエイリアスを導出します。`@rules/product/design-system.md` を適用します。コントラストのゲートを実行します。
3. **組み込みモード（Incorporate mode）** — `--import` を読み取ります。その値を DTCG スキーマ（カラー、タイポグラフィ、スペーシング、角丸など）にマッピングします。マッピングされていないすべての概念を `TBD` + 未解決の質問として記録します。
4. **トークンの発行（Emit tokens）** — `tokens.json`（DTCG）と、ペアになる `tokens.css`（`:root` 変数）を書き込みます。
5. **コンポーネントのインベントリ作成（Inventory components）** — `CMP-` エントリ（バリアント/ステート）を含む `components.md` を書き込み、**mid** フィデリティの場合はトークンベースの CSS クラスを書き込みます。
6. **ガイドラインの執筆（Write guidelines）** — 使用法、アクセシビリティ、トーン＆マナー（voice & tone）。
7. **マニフェスト + プレビュー（Manifest + preview）** — `manifest.json`（`version` を含む）を書き込みます。`preview.html`（トークン + コンポーネントギャラリー、自己完結型）をレンダリングします。
8. **アクティベート（Activate）** — `work/pipeline-progress.json` → `options.design_system = "{name}"` を設定します。
9. **トレーサビリティの追記** — 上流の `POS-`/`PER-` 参照（構築）または `source` 出所（組み込み）を持つ `DS-`/`TOK-`/`CMP-` ノードを `work/traceability.json` に追加します。
10. **記録** — 決定事項を `work/context.md` に追記します。すべての `TBD` をログに記録します。

## Output

`design-system/{name}/` — `tokens.json`、`tokens.css`、`components.md`、`guidelines.md`、`manifest.json`、`preview.html`。`reports/` からは個別に管理されます。`options.design_system` はアクティブなシステムを指します。Frontmatter/JSON のキーは英語のままです。ガイドラインの文章は `options.output_language` を使用します。

> Note: `design-system/` は（実行ごとの `reports/` ツリーとは異なり）耐久性のある個別にバージョン管理されるアセットです。バージョン管理にコミットするかどうかはプロジェクトごとに決定してください。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/design-system.md` | レイヤードモデル、DTCG フォーマット、構築 vs 組み込み、フィデリティ、a11y |
| `@rules/product/positioning-kano-hook.md` | トークンの選択に情報を提供するブランドの個性 / 魅力的品質 |

委譲できる生成エンジン: `example-skills:theme-factory`, `example-skills:brand-guidelines`, `example-skills:frontend-design`, `design-html`。

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:design-positioning` | Upstream — ブランドの個性がトークンに情報を提供します（構築モード） |
| `/product:generate-persona` | Upstream — アクセシビリティのニーズがトークンを制約します |
| `/product:generate-ui-mock` | Downstream — `tokens.css` を注入し、lo/mid フィデリティでレンダリングします |
| `/product:adapt-change` | ブランドまたはインポートされたシステムが変更されたときにこの Skill を再実行します |
