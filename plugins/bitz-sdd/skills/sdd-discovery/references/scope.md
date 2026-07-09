# スコープ（制約 → Kano → RICE → MoSCoW → In/Out 境界）

推奨順: 制約の棚卸し → Kano（情緒的価値の分類）→ RICE（定量ランク）→ MoSCoW（帯域分け）→ In/Out-of-Scope 境界の明文化。作業表は `.spec/discovery/worksheet.md`、結論（Won't と制約）は docs/01-context/non-goals.md と constraints.md の proposed 更新へ。

## 制約の棚卸し（最初にやる）

各制約を分類する: 予算 / 期限 / 技術 / 法規制 / 組織。**スコープ項目は制約に違反してはならない** — 違反するなら理由を明示して却下または延期。制約の結論は constraints.md ドラフトへ（要件 CON への採番は Design Gate 後の派生で行う。ここでは採番しない）。

## Kano（情緒的価値の分類）

- **Must-be（当たり前品質）** — なければ不満、あっても中立 → PoP（競争参加条件）
- **Performance（一元的品質）** — 良いほど満足が線形に増える
- **Attractive（魅力品質）** — 期待されていない価値。あれば喜ばれ、なくても許される → PoD 候補
- Indifferent / Reverse は投資しない

優先: Attractive > Performance > Must-be の閾値充足。**魅力品質は時間とともに当たり前品質に劣化する**ので、差別化セットは継続的に更新する前提で考える。

## RICE（定量ランク）

```
RICE = (Reach × Impact × Confidence) ÷ Effort
```

- **Reach** — 期間あたりの影響ユーザー数（絶対数）
- **Impact** — 3=massive / 2=high / 1=medium / 0.5=low / 0.25=minimal。**Impact は必ず成功指標（NSM/入力指標）を参照する** — 感覚ではなく。指標が未確立なら根拠を `TBD` と明記
- **Confidence** — 100%=high / 80%=medium / 50%=low
- **Effort** — 人月

## MoSCoW（帯域分け）

| 帯 | 意味 |
|---|---|
| **Must** | 譲れない。なければプロダクトが成立しない。MVP に対応 |
| **Should** | 価値は高いが、期限が滑るなら外せる |
| **Could** | あれば嬉しい磨き込み。時間が足りなければ最初に切る |
| **Won't（今回は）** | **明示的に延期。除外を名指しすることがスコープクリープを止める** |

規律: 厳密に運用しないと帯は意見に流れる。「これ以外を全部出荷したら成功指標は達成できるか?」で Must を判定する。

## In-Scope / Out-of-Scope 境界（必須）

明示的な表を作る。**Out-of-Scope（Won't）リストは必須** — スコープクリープに対する最も効果的なガードであり、関係者合意の最も明確な成果物。Won't の結論は non-goals.md ドラフトに「なぜやらないか」つきで転記する。
