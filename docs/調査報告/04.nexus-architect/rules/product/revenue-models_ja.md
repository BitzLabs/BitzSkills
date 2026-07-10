# Rules: Revenue & Market Models (research-landscape, design-revenue)

市場規模の算定（market sizing）および収益/ビジネスモデルのためのリファレンスである。`research-landscape`は**Market sizing**および**Revenue model taxonomy**セクションを使用する。`design-revenue`は**Business model canvas**、**Unit economics**、および**Value hypothesis**を使用する。

## Market sizing — TAM / SAM / SOM

- **TAM** (Total Addressable Market) — 100%のシェアを持っていた場合の総需要。
- **SAM** (Serviceable Available Market) — 製品/セグメント/地域が提供可能な市場のスライス。
- **SOM** (Serviceable Obtainable Market) — 短期的に獲得可能な現実的なシェア。

トップダウンの「大きな数字のX%」よりも、**ボトムアップ**の規模算定（ターゲット顧客数 × 価格 × 頻度）を優先する。すべての数値にはソース（名前とURL）を記載する。ソースのない数値は記述してはならない — それらはOpen Questions内で`TBD`となる。

## Revenue model taxonomy

一般的なパターン: サブスクリプション/SaaS、従量課金/メーター制、トランザクション/テイクレート（手数料）、ライセンス供与、フリーミアム → 有料化、マーケットプレイス、広告、サービス。選択基準: 価値の提供方法との適合性、顧客の支払意志/支払能力、セールスモーション、およびマージン構造。単にどれを選ぶかだけでなく、*なぜ*選択したモデルが創出される価値に適合するのかを明記する。

## Business model canvas / Lean Canvas (9 blocks)

- **BMC (Osterwalder)**: Customer Segments、Value Propositions、Channels、Customer Relationships、Revenue Streams、Key Resources、Key Activities、Key Partners、Cost Structure。
- **Lean Canvas (Maurya)** は、初期段階のリスクに対処するため、4つのブロックをProblem、Solution、Key Metrics、Unfair Advantageに置き換える（Customer Segments、Value Prop、Channels、Revenue Streams、Cost Structureは維持する）。新規/不確実な製品にはLean Canvasを優先する。

## Unit economics (set up as a recomputable template, not a verdict)

- **LTV** = ARPA × 粗利益率 × 平均顧客ライフタイム（または ARPA × 利益率 ÷ チャーンレート）。
- **CAC** = 総販売・マーケティング費用 ÷ 獲得した新規顧客数。
- **LTV:CAC ≥ 3**が健全なベンチマークである。ほとんどのSaaSにおいて**CAC payback < 12 months**である。
- より大きな賭けのための**ROI / NPV**（将来のキャッシュフローを割り引く）。

> **価格とCACは前提条件（assumptions）であり、算術ではない。** これらを`TBD-assumption`として記録し、市場でテストするため（例: Van Westendorp、プレセールス）に`/product:validate-assumptions`に渡す — スプレッドシートの出力を事実として提示してはならない。このテンプレートは、実際の証拠が届いたときに計算を*再計算可能*にするものである。

## Value hypothesis

各ビジネス上のメリットを反証可能なステートメントとして組み立てる: **「Xをリリースすれば、期間T以内に指標YがZ%動く」** — `NSM-`指標を参照する。それぞれについて、どのように検証されるかをペアにする。

## ID convention

収益ストリームとベネフィットの仮説には`REV-xxx`を付与する。Upstreamの`VIS-`/`NSM-`参照とともに`work/traceability.json`に追記する。`market-landscape.md`内の市場に関する事実は、インラインでソースを引用する。

## Sources

- Osterwalder — "Business Model Generation" (Business Model Canvas)
- Ash Maurya — "Running Lean" (Lean Canvas)
- David Skok — "SaaS Metrics 2.0" (LTV:CAC, CAC payback)
