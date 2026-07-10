---
description: |
  ナビゲーション可能な UI モックを実行可能な React フロントエンドに変換します — アクティブなデザインシステムに対して、Atomic Design（アトミックデザイン）（tokens -> atoms -> molecules -> organisms -> templates -> pages）を使用して画面を分解し、Design Tokens（CSS Modules + CSS変数を介して）によってスタイル設定された TypeScript React コンポーネントを生成し、react-router でストーリーのフローを接続し、すべてのコンポーネントを Storybook にバリアント/ステートごとのストーリーとともに登録します。generated/frontend/ の下に、自己完結型のインストール可能なスキャフォールドを出力します。
  /product:generate-frontend [--design-system=<name>] [--out=<path>] [--auto] [--lang=ja|en]。
model: sonnet
user_invocable: true
---

# Frontend Code Generation (React + Storybook)

## Desired Outcome

1つの成果物を作成します：**`generated/frontend/`** の下にある、エンジニアが追加の配線なしで `npm install && npm run storybook`（または `npm run dev`）できる、実行可能な React + TypeScript フロントエンドスキャフォールド。これは UI モックの**実装（implementation）**です — モックは*各画面が何をしてどのような順序で進むか*を示し、デザインシステムは*視覚的言語*を提供し、この Skill はその両方を **Atomic Design** によって整理された、再利用可能でストーリーによって裏付けられた React コンポーネントに変換します。

1. **Atomic Design コンポーネントライブラリ** — `generated/frontend/src/components/` は `atoms/`, `molecules/`, `organisms/`, `templates/` に分割されます:
   - デザインシステムの `components.md` からの各 `CMP-` は、適切なアトミックレベルのコンポーネントになります（プリミティブ → atoms。構成されたもの → molecules/organisms。ページレイアウト → templates）。
   - コンポーネントごと: `Component.tsx`（コンポーネントのバリアント/ステートから型付けされた props）、`Component.module.css`（**Design Tokens のみ**を参照し、決して生の値を使用しないスタイリング）、および `Component.stories.tsx`。
2. **ページ + ルーティング** — `src/pages/`（UIモック画面ごとに1つのページ）および `src/app/router.tsx`:
   - 各 `{STORY}-NN-{slug}.html` モック → templates/organisms から構成される `Page` コンポーネント。
   - ストーリーのフロー（`next`/`prev`）は **react-router** で接続され、モックのクリックスルーパスが実際のナビゲーションになります。欠落しているステップは、行き止まりではなく無効化された `TBD` ルートとしてレンダリングされます。
3. **トークンテーマ（Token theme）** — `src/styles/tokens.css`（アクティブなデザインシステムの `tokens.css` からコピーされたもの）がグローバルにロードされ、`preview` デコレータを介して Storybook に注入されるため、アプリとストーリーは1つの視覚的言語を共有します。
4. **Storybook 登録** — `.storybook/{main.ts,preview.ts}` と、コンポーネントごとの `*.stories.tsx` があり、`components.md` で宣言された**バリアント/ステート**ごとに1つのストーリー（props から派生した args/controls）が含まれます。ページにもストーリーが割り当てられます。
5. **実行可能なスキャフォールド（Runnable scaffold）** — `package.json`、`vite.config.ts`、`tsconfig.json`、および `index.html` エントリがあり、一貫した React 18 + Vite + Storybook 8 + TypeScript ツールチェーンに固定されています。

## Invocation

```
/product:generate-frontend [--design-system=<name>] [--out=<path>] [--auto] [--lang=ja|en]
```

| Argument/Flag | Required | Description |
|---------------|----------|-------------|
| `--design-system=<name>` | Optional | アクティブなデザインシステムをオーバーライドします。デフォルト: progress ファイルの `options.design_system`。 |
| `--out=<path>` | Optional | 出力ルート。デフォルトは `generated/frontend/`。 |
| `--auto` | Optional | ファシリテーションなしで生成します。すべての曖昧さは最も正当化されたデフォルトで解決し、それをログに記録します。 |
| `--lang` | Optional | 出力言語（UIコピー/コメント）を上書きします。コードの識別子は英語のままです。 |

## Decision Criteria

- **Atomic Design は分解であり、デザインシステムは部品の供給源です。** 各 `CMP-` を正確に1つのアトミックレベル（atom/molecule/organism）にマッピングし、各 UIモック画面をテンプレート + ページにマッピングします。`CMP-` や画面の起源を持たないコンポーネントを発明しないでください。画面がデザインシステムに欠けている部品を必要とする場合は、推測されるレベルでそれを生成し、未解決の質問（Open Question）とともに `TBD` のフラグを立てます。
- **トークンのみであり、決して生の値ではありません。** すべての `*.module.css` は `tokens.css` の `var(--token-*)` を参照します。ハードコードされたカラー/スペース/タイプの値は欠陥です。アクティブなデザインシステムがない場合 → モックからアドホックな lo-fi スタイリングをコピーし、トークンテーマが適用されなかったことを書き留めます。
- **モックのクリックパスがルーティングになります。** ページのルートとその `next`/`prev` リンクは、モックのファイル名（`{STORY}-NN-{slug}.html`）にエンコードされたストーリーの順序に従います。ストーリーのギャップは無効な/`TBD` ルートであり、行き止まりにはなりません — モックのナビゲーション可能の契約を反映します。
- **すべてのコンポーネントはストーリーによって裏付けられます。** 各コンポーネントには `components.md` のバリアント/ステートごとに1つのストーリーを持つ `*.stories.tsx` があります。props/controls は型付けされています。ストーリーのないコンポーネントは不完全です。
- **スキャフォールドは実際に実行できなければなりません。** 依存関係のバージョンは互いに互換性があり、固定されています。生成された `package.json` のスクリプト（`dev`, `build`, `storybook`, `build-storybook`, `typecheck`）が存在し、正しい必要があります。機能の幅広さよりも、小さく一貫したツールチェーンを優先します。
- すべてのコンポーネントをその `CMP-`/`TOK-` に、すべてのページをその `STORY-`/画面に**トレースする**こと。
- **終了条件（Stop condition）**: すべての `CMP-` が型付けされた React コンポーネント + そのバリアント/ステートをカバーするストーリーを持っていること。すべての UIモック画面がページ + `router.tsx` 内のルート + ストーリーを持っていること。`tokens.css` がグローバルに、かつ Storybook のプレビューに配線されていること。`package.json`/`tsconfig`/`vite.config`/`.storybook` が存在すること。スキャフォールドが生成されたソースに対して型チェック（論理的に検証）されていること。トレーサビリティが追記されていること。

## Prerequisites

| Input | Required/Recommended | Source | If missing/empty |
|-------|---------------------|--------|------------------|
| `reports/02_spec/ui-mocks/` | Required | `/product:generate-ui-mock` | 停止して報告する — 実装する画面がありません |
| `design-system/{active}/tokens.css` + `components.md` | Recommended | `/product:design-system` | モックから推論された atoms とアドホックな CSS で進めます。トークンテーマ/コンポーネントが利用できなかったことを書き留めます |
| `reports/02_spec/feature-list.md` | Recommended | `/product:define-features` | 進行します。モックから直接画面アクションを導出し、基礎が薄いことを書き留めます |
| `work/traceability.json` | Recommended | `/product:init-output` | 進行します。上流のエッジなしでページ/コンポーネントノードを作成し、それを書き留めます |

## Process

1. **コンテキストの読み取り** — UIモック（`reports/02_spec/ui-mocks/*.html` + ストーリーごとの `*-index.html`）、アクティブなデザインシステム（`options.design_system` → `design-system/{name}/tokens.css`, `components.md`, `manifest.json`）、`feature-list.md`、および `work/traceability.json`。`@rules/product/atomic-react-storybook.md` を適用します。
2. **コンポーネントの分類（Atomic Design）** — 各 `CMP-` について、その構成から atom/molecule/organism を決定します。各 UIモック画面について、そのテンプレート（レイアウト）とページを決定します。マッピングテーブル（`CMP-`/画面 → アトミックレベル → ファイルパス）を記録します。
3. **トークンテーマの解決（Resolve the token theme）** — アクティブな `tokens.css` を `src/styles/tokens.css` にコピーします。利用可能な `var(--token-*)` のリストを構築します。システムがない場合 → モックから導出されたアドホックな CSS にフォールバックします（注記あり）。
4. **atoms → molecules → organisms の生成** — それぞれについて、下位レベルから上位へと構成しながら、`Component.tsx`（バリアント/ステートから型付けされた props）、`Component.module.css`（トークンを参照）を記述します。
5. **templates と pages の生成** — 各画面レイアウトをテンプレート（データなし）に変換し、各画面をページ（テンプレート + organisms + `feature-list.md` からの画面アクション）に変換します。
6. **ルーティングの配線（Wire routing）** — モックファイル名のストーリー順序に従って `src/app/router.tsx`（react-router）を生成します。欠落しているステップは無効な/`TBD` ルートとしてレンダリングします。`next`/`prev` ナビゲーションを追加します。
7. **Storybook の執筆** — `.storybook/main.ts` + `.storybook/preview.ts`（`tokens.css` をインポートし、テーマデコレータを適用します）。コンポーネントごとに1つの `*.stories.tsx`（バリアント/ステートごとに1つのストーリー）、およびページごとに1つ。
8. **スキャフォールドの発行（Emit the scaffold）** — `package.json`（固定された React 18 + Vite + Storybook 8 + TS、`dev`、`build`、`storybook`、`build-storybook`、`typecheck` スクリプトを含む）、`vite.config.ts`、`tsconfig.json`、`index.html`、`src/main.tsx`、`src/App.tsx`。
9. **検証（Verify）** — すべての `CMP-`/画面がコンポーネント/ページ + ストーリーを生成したか、インポートが解決されているか、props/ストーリーが一貫しているか、`*.module.css` に生の値が使用されていないかを論理的にチェックします。すべての `TBD` をリストアップします。
10. **トレーサビリティの追記** — コンポーネントノード（Upstream `CMP-`/`TOK-`）とページノード（Upstream `STORY-`/画面、`next`/`prev` ルートエッジ付き）を `work/traceability.json` に追加します。
11. **記録** — すべてのファイルを書き込みます。コンポーネントのマッピング決定とすべての `TBD` を `work/context.md` に追記します。

## Output

`generated/frontend/` — 実行可能な React + TypeScript + Vite + Storybook スキャフォールド: `src/components/{atoms,molecules,organisms,templates}/`, `src/pages/`, `src/app/router.tsx`, `src/styles/tokens.css`, `.storybook/`, `package.json`, `vite.config.ts`, `tsconfig.json`。各コンポーネント/ページは `*.stories.tsx` を持ちます。スタイリングは Design Tokens のみを参照します。ルーティングはモックのストーリーフローを反映します。コードの識別子は英語のままです。UIコピー/コメントは `options.output_language` を使用します。

## Reference Materials

| Resource | Purpose |
|----------|---------|
| `@rules/product/atomic-react-storybook.md` | CMP-↔アトミックレベルのマッピング、トークン→CSS変数の配線、React/Storybookの規則、フローからのルーティング規則 |
| `@rules/product/design-system.md` | 分解が読み取るトークン/コンポーネントのレイヤードモデル |
| `@rules/product/ui-to-domain.md` | 画面/フローがどのように導出されたか（上流のコンテキスト） |

委譲できる生成エンジン: `example-skills:frontend-design`, `example-skills:web-artifacts-builder`, `mcp__magic__21st_magic_component_builder`。

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:generate-ui-mock` | Upstream — その画面/フローがページ + ルーティングになります |
| `/product:design-system` | Upstream — その `tokens.css`/`CMP-` がテーマ + コンポーネントになります |
| `/product:define-features` | Upstream — 画面アクションがページハンドラになります |
| `/product:adapt-change` | モックまたはデザインシステムが変更されたときにこの Skill を再実行します |
