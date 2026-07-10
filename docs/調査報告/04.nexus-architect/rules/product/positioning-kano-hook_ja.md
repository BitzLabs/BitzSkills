# Rules: Positioning, Kano & Hook (research-landscape, design-positioning)

競合分析および差別化のためのリファレンスである。`research-landscape`は、差別化戦略を推奨するために**Competitive matrix**、**PoD / PoP**、および**Kano**の各セクションを使用する。`design-positioning`はさらに**Positioning statement**と**Hook model**を使用する。

## Competitive matrix

直接競合、間接競合、および現状維持の代替手段（「何もしない」/ スプレッドシートを含む）をリストアップする。ターゲットセグメントにとって重要な次元（機能、価格、セグメントの焦点、チャネル）で比較する。各競合他社は名前とURLを引用する。目的は機能のチェックリストを作成することではなく、ホワイトスペース（空白地帯）を見つけることである。

## Points of Difference (PoD) vs Points of Parity (PoP)

- **PoP (points of parity)** — 検討されるために満たす必要がある最低限（table-stakes）の属性。これらを満たすことは「買わない理由を取り除く」ことであり、上回ったとしても勝利に繋がることは稀である。**ここに過剰投資してはならない。**
- **PoD (points of difference)** — 意味のある形で優れている/異なっており、セグメントが価値を見出す属性。これは投資が選好へと複利で増大する領域である。

戦略: PoPについては効率的にパリティ（同等性）に到達し、防御可能な少数のPoDにリソースを集中させる。

## Kano model

候補となる属性を分類する:

- **Must-be (basic)** — なければ不満を引き起こすが、あってもニュートラルである → これらは**PoP**である。
- **Performance (one-dimensional)** — 満足度は、それをどれだけうまく行うかに比例して線形にスケールする。
- **Delighter (attractive)** — 予期せぬ価値。あると喜びを与え、なくても許容される → これらは**PoD**である。

Delighter（魅力的品質）は時間の経過とともに期待へと劣化する（今日のDelighterは明日のMust-beである）。そのため、1回限りのリストではなく、差別化セットの継続的な更新を推奨する。

## Positioning statement (Moore template) — quick form

> **[need/opportunity]**である**[target segment]**にとって、**[product]**は**[key benefit / reason to believe]**を提供する**[category]**である。**[primary alternative]**とは異なり、我々の製品は**[primary differentiation = the PoD]**である。

## Positioning canvas (April Dunford) — 5 components

`design-positioning`のために使用する。ポジショニングは*意図的*なものであり、以下の順序で導き出される:

1. **Competitive alternatives** — あなたが存在しなかった場合に顧客が行うこと（現状維持を含む）。
2. **Unique attributes** — 代替手段には欠けているが、あなたが持っている能力。
3. **Value (and proof)** — それらの属性が可能にする顧客の**成果（outcome）**。機能ではなく、*価値*を主張する。
4. **Target segment / characteristics** — その価値を最も気にかけるのは誰か（最適にフィットする顧客）。
5. **Market category** — そのセグメントにとってその価値を明白にするための、参照の枠組み。

機能リストではなく、**価値（顧客の成果）**を主張すること。PoP（points of parity）で戦ってはならない。

## Engagement & retention design (Fogg + Hook)

`design-positioning`のモチベーション/リテンションレイヤーについて:

- **Fogg Behavior Model**: Behavior（行動） = **Motivation（モチベーション） × Ability（能力） × Prompt（プロンプト）**であり、すべてが同時に存在する必要がある。*アクティベーション/モチベーション*のステップで使用する — 必要な能力を下げ（摩擦を減らし）、適切なタイミングで明確なプロンプトを配置する。
- **Hook model (Nir Eyal)**: Trigger（トリガー） → Action（行動） → Variable Reward（変動報酬） → **Investment（投資）**。*リテンション*に使用する — Investmentのステップは、ループが複利で増大するようにスイッチングコスト（データ、コンテンツ、ネットワーク）を蓄積する必要がある。各ループは`NSM-`のリテンション/エンゲージメント入力指標を動かさなければならない。
- **ダークパターンを避けること。** エンゲージメントは価値を通じて獲得されるものであり、強制や欺瞞的なUXによるものではない。

## Touchpoint × device × timing matrix

`journey-maps.md`から機会/タッチポイントを取り出し、タッチポイントごとに**デバイス**（モバイル/デスクトップ/製品内/メールなど）と、意図されたメッセージのための**タイミング**（どのジャーニーステージ / 瞬間か）を割り当てる。これは、ポジショニングをそれが実際に伝達される場所とタイミングに結びつける。

## ID convention

ポジショニングの主張と選択されたPoDには`POS-xxx`を付与する。Upstreamの`VIS-`/`NSM-`参照とともに`work/traceability.json`に追記する。`market-landscape.md`内の競合に関する事実は、インラインでソースを引用する。

## Sources

- Kotler/Keller — Points of Difference / Points of Parity
- Noriaki Kano — Kano model of customer satisfaction
- Geoffrey Moore — "Crossing the Chasm" positioning template
- Nir Eyal — "Hooked" (Hook model)
