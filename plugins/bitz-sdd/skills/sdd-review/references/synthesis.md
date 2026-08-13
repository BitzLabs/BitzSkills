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

**成果物の正は番号付きの `.spec/reviews/<REV-ID>.json` / `.md`**。
`review-synthesis.json` と `_review-synthesis.md` は最新へのビューであり、自前の成果物 ID も
finding も持たない（SDD-FR-160）。Markdown 側を `_` 始まりにするのは、`_` 始まりを成果物として
走査しないという既存規約に乗せて、**古い bitz-sdd を固定版として消費しているワークスペースでも
「id が無い」FAIL を起こさない**ため。
先に番号付きファイルを作り、そのあとビューのリンクを差し替える。順序を逆にすると
`spec_inspect` が**アーカイブ漏れ**として FAIL させる。

- `.spec/reviews/<REV-ID>.json`（`schema_version: 2`。この schema は機械検証される）:

```
{
  "schema_version": 2,
  "review_id": "<REV-ID>",
  "verdict": "PASS|CONDITIONAL_PASS|FAIL",
  "aggregate_score": <小数2桁>,
  "perspective_scores": {"<観点>": <score>, ...},
  "findings_summary": {"total": <統合前件数>, "after_dedup": <統合後>, "by_priority": {}, "by_severity": {}},
  "findings": [...],            // 下表の必須キー
  "gate_preconditions": [...],  // 下表の必須キー
  "carried_over": [],           // 過去レビューから引き継いだ未消化の P0/P1
  "conditional_items": []
}
```

### findings[] の必須キー（SDD-FR-158）

| キー | 値 |
|---|---|
| `id` | **`<REV-ID>:SYN-NNN`** — レビュー横断で一意にする（レビュー内連番だけでは別レビューの同番号と区別できない） |
| `priority` | `P0` / `P1` / `P2` / `P3` |
| `severity` | `critical` / `major` / `minor` / `info` |
| `source` | 観点別 finding ID の配列（旧 `source_ids` を統一） |
| `title` | 短い要約 |
| `recommendation` | 実行可能な是正内容 |
| `tracked_by` | SpecIssue ID または `<REV-ID>:GP-NNN`。**P0/P1 は必須**（P2/P3 は空文字でよいがキーは置く） |
| `status` | `open` / `tracked` / `resolved`（持ち越し判定に使う） |

**未紐づけの P0/P1 がある状態で `verdict: PASS` を出せない**（SDD-FR-159）。`tracked_by` は
実在検査の対象で、spec-issue は全ワークスペース横断で、`<REV-ID>:GP-NNN` は同一レビューの
`gate_preconditions` に対して解決される。

### gate_preconditions[] の必須キー（SDD-FR-161）

| キー | 値 |
|---|---|
| `kind` | **`blocking`**（Gate 通過前に消化する条件）/ **`agenda`**（Gate で決める論点） |
| `basis` | **`verified`**（実測で確認済み）/ **`assumed`**（未検証の想定） |
| `evidence` | `basis: verified` のとき必須。実測の所在 |
| `gp_kind` | 新規 GP で必須。**`behavioral`** / **`artifact`** / **`process`**。既存レビューは段階移行のため欠落を許容 |
| `ears` | `gp_kind: behavioral` のとき必須。`WHEN` 節と `SHALL` を含む振る舞い契約 |
| `response` | 分類済み `blocking` GP で必須。下記の受領応答 |

**不変条件: `basis: assumed` を根拠に `kind: blocking` は立てられない**。Gate 通過の阻止に
使うのは `kind: blocking` かつ未消化のものだけで、`agenda` は阻止に使わない。
この区別が無いと「前提条件なのに Gate で決めること」という循環が起きる。
`artifact` / `process` へ形式だけの EARS 文を作ってはならない。EARS は実行時の振る舞いを要求する
`behavioral` GP に限定し、成果物や作業手順の条件は `statement` で記述する。

### blocking GP の response（SI-SDD-042）

すべての応答は `original` にGP原文を逐語転記する。`behavioral` では `ears`、それ以外では
`statement` と完全一致しなければならない（段階移行中の旧レビューは `condition` も受理する）。
状態別の必須キーは次のとおり。

| `status` | 必須キー | 意味 |
|---|---|---|
| `accepted` | `original`, `normalized`, `target` | 意味を保った表現と実現先を宣言する |
| `rejected` | `original`, `reason`, `rereview` | 却下理由と独立した再レビュー先を宣言する |
| `deferred` | `original`, `tracking_target`, `deadline`, `gate` | 追跡先、ISO日付の期限、再判定Gateを宣言する |

`deferred.gate` は `discovery` / `design` / `promotion` のいずれかとする。この構造化検査は
独立レビューの代替ではなく、レビュー指摘を別の意味へ取り違えないための受領証跡である。

### 持ち越し（carried_over）

新しい synthesis を生成するときは、過去の全 `.spec/reviews/<REV-ID>.json` から
`status` が `resolved` でない `P0` / `P1` の finding を `carried_over[]` へ取り込む
（要素は `<REV-ID>:SYN-NNN`。取り込み元の実在が検査される）。手作業の追跡表に頼らない。

- `.spec/reviews/<REV-ID>.md`: 書式は assets/review-report.md をコピーして使う（記憶から書き起こさない）

判定・レポートを人間に提示して終了。裁定（Design Gate / Promotion Gate の通過）は人間が行う。

### 既存レビューの扱い

`schema_version` を持たないレビューは本 schema の検査対象外とし、遡及的に不整合としない。
アーカイブ漏れの検査だけは `schema_version` の有無にかかわらず適用される。
