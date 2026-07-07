# ビジョン（Vision Board + PR-FAQ）

両方使う: Vision Board が核を定め、PR-FAQ が圧力試験する。結論は docs/01-context/mission-vision.md の proposed 更新に落とす。

## Product Vision Board（Roman Pichler）— 5要素

1. **Vision** — 究極の目的。プロダクトが世界に起こす変化。野心的で記憶に残る1文
2. **Target Group** — ユーザーと顧客。**必ずセグメントする — 「みんな」は禁止**
3. **Needs** — 解決する問題/届ける便益。なぜ乗り換えるのか
4. **Product** — 際立つ少数の機能・差別化要素（機能全リストではない）
5. **Business Goals** — 会社にとっての便益（収益・成長・維持）

良いビジョンは: 野心的・鼓舞する・共有される・簡潔で記憶に残る。

**Mission / Vision / Values の区別**: Vision = 目的地（世界の変化）。Mission = 日々の追求方法（何を・誰のために・どうやるか）。Values = トレードオフ時の判断原則。埋めた Vision Board から Mission と Values を導出する。

## Working Backwards — PR-FAQ（Amazon）

**すでに出荷された体で書く。売り込みではなく真実の探求。**

プレスリリース（約1ページ）:

- 見出し（プロダクト名）/ 小見出し（ターゲット顧客 + 中核便益を1行）
- 要約段落（何か・誰のためか・見出しの便益）
- 問題段落 — 顧客の痛みを**顧客の言葉で**
- 解決段落 — どう解決するか・**差別化**は何か
- 引用と CTA — 責任者の言葉 + 顧客の言葉 + 始め方

FAQ（2層）:

- **外部 FAQ** — 価格・機能・購入方法・サポート
- **内部 FAQ** — 市場規模（TAM/SAM/SOM）・競合状況・ユニットエコノミクス・運用課題・リスク・**Go/No-Go 基準**

> **Go/No-Go 基準は荷重を受ける部材**: 後段の仮説検証ゲート（references/assumption-gate.md）がこれを執行する。具体的かつ反証可能に書く（例: 「インタビューしたターゲットの X% がこの問題をトップ3に挙げたら Go」）。

## ドラフトへの落とし込み

- Mission / Vision / Values の結論 → mission-vision.md（proposed 更新）
- PR-FAQ 全文と TAM/SAM/SOM 等の作業内容 → `.planning/discovery/pr-faq.md`（短命）
- Go/No-Go 基準 → 仮説として `.planning/discovery/worksheet.md` の仮説表に転記
- 根拠のない数値は書かず `TBD` として Open Questions に残す
