# Rules: Design System (design-system, consumed by generate-ui-mock)

プロダクトパイプラインにおいてデザインシステムを構築し、組み込むためのリファレンスである。デザインシステムは**「どのように見えるか」のレイヤー**である。Domain Story (ドメインストーリー)が画面が「何を」「どの順序で」行うかを決定するのに対し、デザインシステムはすべての画面が共有する*視覚的言語*を決定する。それはプロジェクト間で再利用、バージョン管理、入れ替えができるように、単一のパイプライン実行から**分離して**管理される。

## Layered model (each layer depends on the one below)

```
Guidelines / Usage   — when to use what; accessibility; voice & tone
Patterns             — form, table, empty/loading/error states, navigation
Components           — Button / Input / Card / Modal … (variants + states)
Primitives           — Box / Stack / Text (layout atoms)
Design Tokens        — color / typography / spacing / radius / elevation / motion   ← foundation
```

**トークンが基盤である。** 単一のトークンソースを使用することで、すべてのモックを自己完結させつつ視覚的な一貫性を保つことができる（同じトークンCSSが各HTMLファイルに注入される — 共有の外部アセットは存在しない）。

## Two modes

- **Build (greenfield (新規開発))** — `positioning`（ブランドの個性 / Kanoモデルの魅力的品質）、`personas`（アクセシビリティのニーズ：コントラスト、ターゲットサイズ、動きの感受性）、および`vision`（トーン）からトークンを導出する。基本となる色相 + スケール、タイポグラフィスケール、スペーススケール（例：4/8 pxベース）、角丸/エレベーションのステップを選択し、セマンティックなエイリアス（`color.bg`, `color.fg`, `color.primary`, `color.danger`, …）を生成する。
- **Incorporate (brownfield)** — `--import=<path>`は既存のシステムを読み込み、**同じトークンスキーマに正規化する**。Tailwind設定、W3C DTCG JSON、Figma Tokensエクスポート、またはCSS/SCSS変数のテーマ（MUI/Chakra）が対象である。マッピングされていない値 → Open Questionを伴う`TBD`とする。ブランドの値を無言で発明してはならない。

どちらのモードも**1つのDTCGトークンファイル**に収束するため、下流のツールは同一である。

## Token format — W3C DTCG

Design Tokens Community Group (DTCG) フォーマットを使用する（`$value`, `$type`, `$description`。カテゴリごとにグループ化する）。これは相互運用可能であり、Style Dictionaryを介してCSS変数、Tailwind、またはネイティブコードに変換できる。

```json
{
  "color": {
    "primary": { "$type": "color", "$value": "#2563eb", "$description": "Primary brand / CTA" },
    "bg":      { "$type": "color", "$value": "#ffffff" },
    "fg":      { "$type": "color", "$value": "#0f172a" }
  },
  "space": { "2": { "$type": "dimension", "$value": "8px" } },
  "font":  { "body": { "$type": "fontFamily", "$value": ["Inter", "system-ui", "sans-serif"] } }
}
```

モックがCSS変数を介してトークンを利用できるように、ペアとなる`tokens.css`（`:root { --color-primary: #2563eb; … }`）を出力する。

## Separate management

- パイプラインの再実行で上書きされず、プロジェクト間で共有できるように、**専用の`design-system/<name>/`ツリー**（`reports/`の兄弟要素であり、その中ではない）に出力する。
- 各システムは`manifest.json`を保持する：`name`, `version`（セマンティックバージョニング — 変更時に繰り上げ）, `mode`（`built` | `imported`）, `source`, `fidelity_support`, `generated_at`。
- 複数の名前付きシステムが共存できる（テーマ）。アクティブなものは`work/pipeline-progress.json` → `options.design_system`（名前またはパス）に記録される。`generate-ui-mock`はそのポインタを読み取る。存在しない場合 → 場当たり的なlo-fiスタイルにフォールバックする。
- このスキルは**スタンドアロン**である。フルパイプラインの実行とは独立して、いつでも実行できる。

## Fidelity (selectable, consumed by generate-ui-mock)

- **lo** (デフォルト) — トークンCSS（色/スペース/タイポグラフィ/角丸）のみを注入する。Lo-fiなレイアウトだが、一貫したパレット/リズムを持つ。最も安価であり、迅速なイテレーションに適している。
- **mid** — さらに、`components.md`からコンポーネントスタイル（Button/Input/Card/… のクラス）を適用する。画面は実際のUIにより近くなる。生成コストは高くなる。
- いずれの忠実度（fidelity）も同じソースからレンダリングされるように、システムは両方のレイヤーを提供すべきである。

## Accessibility (non-negotiable in build mode)

- 本文テキストのコントラスト ≥ WCAG AA (4.5:1)。大きなテキスト ≥ 3:1。チェックしたペアを記録すること。
- 色だけで意味を表現しないこと（アイコン/ラベルとペアにする）。
- 動きのあるトークンについては`prefers-reduced-motion`を尊重すること。

## ID convention & traceability

デザインシステムには`DS-`、トークンには`TOK-`、コンポーネントには`CMP-`を使用する。上流の参照（`POS-`/`PER-` → `TOK-`/`CMP-`）を伴って`work/traceability.json`に追記する。ui-mock画面は使用する`CMP-`を参照する。

## Tooling / sources

- W3C Design Tokens Community Group format (DTCG)
- Style Dictionary — トークンの変換/エクスポート
- 生成エンジンとして利用可能な既存のハーネススキル：`example-skills:theme-factory`, `example-skills:brand-guidelines`, `example-skills:frontend-design`, `design-html`
