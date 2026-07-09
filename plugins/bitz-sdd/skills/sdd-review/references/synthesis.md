# 統合手順（synthesizer）

観点別 JSON（`.spec/review/individual/*.json`）を単一の統合判定にまとめる。2〜5観点の可変入力で動作する。

## Step 1: 重複排除

複数の観点が同じ根本原因を別角度から指摘することがある。

- **同一箇所 + 同一根本原因** → 1件にマージし、元の全 ID を `source_ids` に記録（例: "RVC-201, BIZ-102"）。severity は最高値を採用し、recommendation は1つの実行可能な項目に統合する
- **同一根本原因 + 別箇所** → 別件のまま `related_to` でリンク
- **別根本原因 + 同一箇所** → 別件のまま

## Step 2: 優先度分類

| 優先度 | 基準 |
|---|---|
| **P0 - Blocker** | severity: critical（データ損失・セキュリティ侵害・システム障害を招く） |
| **P1 - Must Fix** | 2観点以上からの major、または risk 観点の major |
| **P2 - Should Fix** | 1観点のみの major、または3観点以上に共通する minor |
| **P3 - Consider** | minor / info |

## Step 3: ゲート判定

レジストリ（assets/review-registry.json、プロジェクト側 `.spec/review/registry.json` があればそちら）の `quality_gates` に照らす。**有効だった観点の重みを再正規化**（合計1.0に）してから加重集計スコアを計算する:

```
aggregate = Σ( 正規化重み_i × weighted_score_i )
```

- **PASS**: aggregate ≥ 3.5 かつ critical 0 かつ major ≤ 3 かつ全観点 ≥ 3.0
- **CONDITIONAL_PASS**: aggregate ≥ 2.5 かつ critical ≤ 2（軽減策必須）かつ major ≤ 8
- **FAIL**: 上記未満

CONDITIONAL_PASS の場合、通過条件（critical/major への軽減策）を `conditional_items` に列挙する。

## Step 4: レポート生成

- `.spec/review/review-synthesis.json`:

```
{
  "review_id": "<日付-連番>",
  "verdict": "PASS|CONDITIONAL_PASS|FAIL",
  "aggregate_score": <小数2桁>,
  "perspective_scores": {"<観点>": <score>, ...},
  "findings_summary": {"total": <統合前件数>, "after_dedup": <統合後>, "by_priority": {}, "by_severity": {}},
  "findings": [{"id": "SYN-001", "priority": "P0|P1|P2|P3", "source_ids": [], "perspectives": [], "title": "", "recommendation": ""}],
  "conditional_items": []
}
```

- `.spec/review/review-synthesis.md`: 書式は assets/review-report.md をコピーして使う（記憶から書き起こさない）

判定・レポートを人間に提示して終了。裁定（Design Gate / Promotion Gate の通過）は人間が行う。
