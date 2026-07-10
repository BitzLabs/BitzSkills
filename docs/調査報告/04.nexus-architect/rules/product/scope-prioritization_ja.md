# Rules: Scope & Prioritization (define-scope)

`/product:define-scope`のためのリファレンスである。推奨される順序は、Discovery (発見) → Kano (狩野モデル) → RICE → MoSCoW → In/Out-of-Scope boundary (スコープ内/スコープ外の境界) である。

## MoSCoW

| Band (バンド) | Meaning (意味) |
|------|---------|
| **Must-have** | 交渉の余地はない。これがなければプロダクトは失敗する。MVPにマッピングされる。 |
| **Should-have** | 価値は高いが、スケジュールが遅れた場合は省くことができる。 |
| **Could-have** | あれば良い（Nice-to-have）洗練要素。時間が限られている場合、最初に削られる。 |
| **Won't-have (now)** | **明示的に延期される。** 除外するものを名前付けすることが、scope creep (スコープクリープ) を止めるものである。 |

Discipline (規律): 厳格なファシリテーションがなければ、バンドは意見へと流れてしまう。"Must"を目標に結びつけること — もしこの項目以外すべてをリリースした場合、プロダクトは依然としてsuccess metric (成功指標) を達成できるか？

## RICE

```
RICE = (Reach × Impact × Confidence) ÷ Effort
```
- **Reach** — 期間あたりに影響を受けるユーザー数（絶対数）
- **Impact** — 3: massive (非常に大きい) / 2: high (大きい) / 1: medium (中程度) / 0.5: low (小さい) / 0.25: minimal (最小限)。**Impactはsuccess metric（`NSM-`）を参照しなければならない。**フィーリングであってはならない。もし指標がまだ存在しない場合は、根拠を`TBD`とマークすること。
- **Confidence** — 100%: high (高い) / 80%: medium (中程度) / 50%: low (低い)
- **Effort** — person-months (人月)

## Kano (感情的価値を分類する場合)

Must-be (当たり前品質) / Performance (一元的品質) / Attractive (魅力的品質) / Indifferent (無関心品質) / Reverse (逆品質)。
Attractive > Performance > Must-be threshold (しきい値) の順に優先順位を付けること。Delighters (魅力的要素) は時間の経過とともにMust-beへと劣化していく。

## Constraints intake (制約の取り込み)

各constraint (制約) を分類すること: budget (予算) / deadline (期限) / technical (技術的) / legal-regulatory (法的・規制的) / organizational (組織的)。
それぞれに`CON-`のIDを付与すること。**いかなるスコープ項目もconstraintに違反してはならない** — もし違反する場合は、明確な理由とともに却下または延期すること。

## In-Scope / Out-of-Scope boundary (必須)

明示的な表を作成すること。**Out-of-Scope (Won't) リストは必須である** — これはscope creepに対する最も効果的な防御策であり、stakeholder (ステークホルダー) 間の認識を合わせるための最も明確なartifact (成果物) である。

## ID convention (IDの規則)

Constraintsは`CON-`、scope items (スコープ項目) は`SCP-`とし、それぞれにUpstream (上流) カラム（`VIS-`/`NSM-`）を設けること。
すべてのノードを `work/traceability.json` に追記すること。

## Sources (情報源)

- Dai Clegg — MoSCoW (DSDM)
- Intercom — RICE scoring
- Noriaki Kano — Kano model
