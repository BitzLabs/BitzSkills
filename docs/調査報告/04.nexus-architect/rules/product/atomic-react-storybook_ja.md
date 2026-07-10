# Rules: Atomic Design → React → Storybook (generate-frontend)

ナビゲート可能なUIモックとアクティブなデザインシステムを、**Atomic Design**を用いて分解し、**Storybook**に登録された実行可能なReact + TypeScriptフロントエンドへと変換するためのリファレンスである。モックは具体的な画面とフローであり、デザインシステムは視覚的言語とパーツのインベントリである。このレイヤーは*実装（implementation）*であり、各コンポーネントは`CMP-`/`TOK-`に、各ページは`STORY-`/画面に追跡される。

## Atomic Design ↔ source mapping

デザインシステムはすでにレイヤー化されたモデル（トークン → プリミティブ → コンポーネント → パターン → ガイドライン）を宣言している。これを以下のようにAtomic Designにマッピングする。

| Atomic Design level | Source | Examples |
|---------------------|--------|----------|
| **Design Tokens** (基礎) | `design-system/{name}/tokens.css` (`TOK-`) | 色 / スペース / タイポグラフィ / 角丸 / エレベーション |
| **Atoms** | プリミティブ / 単一目的の`CMP-` | Button, Input, Text, Icon, Badge, Label |
| **Molecules** | atomsとシンプルなパターンから構成される`CMP-` | FormField (Label+Input+Error), SearchBar, Card |
| **Organisms** | パターン / 構成されたセクション | NavBar, DataTable, Form, Modal, Header |
| **Templates** | UIモック画面のレイアウト、**データなし** | DashboardLayout, DetailLayout |
| **Pages** | UIモック画面 `{STORY}-NN-{slug}.html` | template + organisms + 実際の/サンプルデータ |

**分類ルール:** `CMP-`内に他の`CMP-`を持たない場合、それは**atom**である。atomsのみで構成されている場合、それは**molecule**である。moleculesやatomsを独立したセクションに構成している場合、それは**organism**である。
画面がデザインシステムで宣言されていないパーツを必要とする場合、推論されたレベルでそれを生成し、Open Questionを伴う`TBD`フラグを立てる。デザインシステムのパーツを無言で発明してはならない。

## Tokens → styling (CSS Modules + CSS variables)

- アクティブな`tokens.css`を`src/styles/tokens.css`にコピーし、それをグローバル（`main.tsx`）**および**`.storybook/preview.ts`で一度だけインポートする。これにより、アプリとストーリーが1つのテーマを共有する。
- すべての`*.module.css`は`var(--token-*)`を介してトークンを参照する。**生の（raw）色/スペース/タイポグラフィの値は欠陥である。** デザインシステムのセマンティックなエイリアス（`--color-primary`, `--space-2`, …）をそのままマッピングする。
- **どのトークンによっても管理されていない構造的な値は許可される。** 例として、`1px`のヘアラインボーダー幅、コンテナの`max-width`、`margin: 0 auto`、`100vh`などは、デザインシステムがその概念のためのトークンを宣言していない場合には許可される。トークンが存在する場合はそれを優先する。繰り返し現れる構造的な値が明らかにトークンを求めている場合（共有のボーダー幅やコンテナ幅など）、リテラルを散在させるのではなく、デザインシステムのためのOpen Questionとして追加する。色、フォントサイズ、スペースは常にトークンでなければならない。
- デザインシステムの忠実度（fidelity）が**mid**の場合、`components.md`から`CMP-`コンポーネントのCSSクラスをコンポーネントの`*.module.css`に移植する。**lo**の場合はトークンのみからスタイルを適用する。
- アクティブなデザインシステムがない場合、モックの場当たり的なインラインCSSをモジュールにコピーし、トークンのテーマが適用されていない（捏造されたパレットがない）ことを記述する。

## Component generation (React + TypeScript)

- 1つのコンポーネントにつき1つのディレクトリを作成する：`Component.tsx`、`Component.module.css`、`Component.stories.tsx`、オプションで`index.ts`（再エクスポート用）。
- **Propsは`components.md`のコンポーネントのバリアント/状態から型付けされる。** 各バリアント → プロパティのユニオン（`variant: 'primary' | 'secondary'`）、各状態 → boolean/enum（`disabled`, `loading`）。
- コンポーネントは**上向きにのみ**構成される（moleculeはatomsをインポートし、organismはmolecules/atomsをインポートする）。下位レベルが上位レベルをインポートすることはない。コンポーネントはプレゼンテーショナルな状態に保つ。ページレベルの状態はページ内に存在する。
- 識別子（コンポーネント名、プロパティ、ファイル名）は**英語**である。ユーザー向けテキストとコメントのみが`options.output_language`を使用する。

## Pages & routing (react-router, from the mock flow)

- 各UIモック画面 → templates + organismsから構成される1つの`src/pages/{Story}/{NN}-{slug}.tsx`ページ。画面のアクションは`feature-list.md`（`FEAT-`）からハンドラー/`<Link>`として提供される。
- `src/app/router.tsx`は**モックのファイル名にエンコードされたストーリー順序**（`{STORY}-NN-{slug}`）でルートを定義する。モックからの`next`/`prev`リンクは`<Link>`ナビゲーションになる。
- モックに欠けているストーリーステップは、決して行き止まりではなく、モックのナビゲート可能性の契約を反映した**無効化された（disabled）`TBD`ルート**（ギャップを記述したスタブページ）としてレンダリングされる。分岐は対象のページにリンクする。
- ストーリーごとのエントリールートは、モックの`{STORY}-index.html`を反映する。

## Storybook registration

- `.storybook/main.ts`: Viteビルダー、`stories: ['../src/**/*.stories.@(tsx|mdx)']`、Reactフレームワークアドオン、essentials。
- `.storybook/preview.ts`: `../src/styles/tokens.css`をインポートする。すべてのストーリーがトークンでレンダリングされるように、テーマラッパーを適用するデコレーターを追加する。
- **コンポーネントごとに1つのストーリーファイル**とし、`components.md`の**バリアント/状態ごとに1つのストーリー**を作成する（`Primary`, `Secondary`, `Disabled`, `Loading`, …）。コントロールが型付けされるように`argTypes`/`args`を使用する。ページにもストーリーを作成する（ルーターデコレーター内でレンダリングされる）。
- `title`を介してストーリーをアトミックレベルでグループ化する（`Atoms/Button`, `Molecules/FormField`, `Organisms/NavBar`, `Pages/{Story}/{Screen}`）。

## Scaffold (runnable, pinned)

- ツールチェーン：**React 18 + Vite + TypeScript + Storybook 8** — バージョンは互いに互換性があり、固定されている。`package.json`のスクリプト：`dev`, `build`, `preview`, `storybook`, `build-storybook`, `typecheck`。
- ファイル：`package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/App.tsx`（ルーターをマウントする）, `src/styles/tokens.css`。
- このスキルは**ソースを出力する**。`npm install`は実行しない。検証は論理的である：インポートが解決可能か、すべての`CMP-`/画面がコンポーネント/ページ + ストーリーを生成したか、props↔ストーリーが一貫しているか、生の（raw）値を使用しているモジュールCSSがないか。

## ID convention & traceability

- Reactコンポーネントには`COMP-`、ページには`PAGE-`を使用する。上流の参照を伴って`work/traceability.json`に追記する：コンポーネント → `CMP-`/`TOK-`。ページ → `STORY-`/画面、および`next`/`prev`ルートのエッジ。
- `CMP-`/画面 → アトミックレベル → ファイルパスの完全なマッピングテーブルと、すべての`TBD`を`work/context.md`に記録する。

## Sources

- Brad Frost — *Atomic Design* (atoms/molecules/organisms/templates/pages)
- W3C Design Tokens Community Group (DTCG) — デザインシステムが出力するトークンフォーマット
- Storybook Component Story Format (CSF 3) — `*.stories.tsx`構造
