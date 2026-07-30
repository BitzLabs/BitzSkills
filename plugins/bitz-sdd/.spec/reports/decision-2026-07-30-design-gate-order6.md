# 裁定記録 — 順序6（GatePassage / ReviewFinding）の Design Gate

- **日付**: 2026-07-30
- **対象ワークスペース**: `plugins/bitz-sdd`
- **裁定者（人間）**: hide
- **対象**: `SDD-DSN-010`（GatePassage・裁定2 の設計）と `SDD-DSN-011`（ReviewFinding・裁定3 の設計）が
  提示した設計裁定点 8件（D1〜D8）
- **裁定の形式**: セッション内の対話裁定。エージェントが各裁定点を選択肢・トレードオフ・推奨つきで
  2回に分けて提示し、裁定者が8件すべてを個別に選択した。**8件とも推奨案が選ばれた**
- **代行実行者（エージェント）**: claude-opus-5
- **前提**: ROADMAP フェーズ3 順序6。加法的な変更のみで構成し、メジャー bump は行わない
  （`decision-2026-07-30-implementation-order.md` 裁定A）

## SDD-DSN-010 — GatePassage

| # | 裁定点 | 採用 |
|---|---|---|
| D1 | GatePassage 成果物の配置 | **`.spec/gates/<NS>-GATE-NNN.md` を新設** |
| D2 | 「未検分の代行遷移」の判定単位 | **`decision_ref` 単位** |
| D3 | `verified → promoted` での GatePassage | **必須にする** |
| D4 | 滞留の閾値宣言 | **可視化のみ先行**（閾値は実測が溜まってから） |

**D2 は SI-SDD-028 提案1 の定義を上書きする**。提案1 は滞留を「対象要件が promoted に達して
いないもの」と定義していたが、代行遷移は spec-issue の `open → accepted` にも起きており
（bitz-sdd の代行18件の多くがこれ）、spec-issue は `promoted` 状態を持たないため永久に
滞留扱いになる。検分の単位を裁定記録に置くことで spec-issue の代行遷移も判定でき、
1つの裁定記録が複数遷移を束ねる実態とも一致する。

**D4 は SI-SDD-029 の轍を踏まないための判断**。`adoption-metrics.md` は `manual-check` 比率
20% という閾値を宣言しながら計算する実装がどこにも無く、実測 42.5% を誰も検知できなかった。
閾値を宣言するなら機械集計と同時に入れる。今回は件数と最古の滞留日数の可視化を先行させる。

## SDD-DSN-011 — ReviewFinding

| # | 裁定点 | 採用 |
|---|---|---|
| D5 | findings の物理形 | **JSON 内の配列のまま**（ID と schema だけ固める） |
| D6 | 未紐づけ P0/P1 検査の置き場 | **`spec_inspect`** |
| D7 | `gate_preconditions.basis` の必須化 | **必須化する** |
| D8 | 既存 SDD-REV-002〜005 の扱い | **検査対象外**（遡及しない） |

**D6 は境界の裁定でもある**。判定は Core（コンテキスト1「仕様ライフサイクル」）が持ち、
コンテキスト6「可視化」は読み取り専用の読取モデルに留める。`sdd_report` へ置くと
「レポートを生成しなければ Gate を通せる」構造になる。

**D7 は SI-SDD-035 提案3 の論点を決着させる**。`basis: assumed` を根拠に `kind: blocking` を
立てられないことを不変条件とする。SI-CORE-038 が未検証の想定を根拠に実装順序の最先行へ
据えられた事故の再発防止であり、SI-SDD-035 の裁定を待たずに設計として確定した。
SI-SDD-035 の残る提案（1・2・4）は引き続き裁定待ちである。

## 本裁定で確定した実装の性質

8件いずれも加法的であり、**STATE event の `schema_version: 2` と `verdict` 算出式は不変**。
これにより順序6 は 3.x のまま実施でき、破壊的変更は順序8 へ寄せる方針（裁定A）が保たれる。

## 派生して確認した事項（裁定ではない）

- **設計ノートの `status` はライフサイクル管理下にない**。`spec_update.py` の `TRANSITIONS` は
  requirement / spec-issue / task の3種のみを持ち、design 種別のエントリが無い。
  `lifecycle.md` が監査対象とする状態（approved / promoted / deprecated / accepted / rejected /
  superseded）にも `active` は含まれない。したがって `draft → active` は CLI 迂回の手編集ではなく、
  遷移経路がそもそも存在しない平坦な frontmatter 項目である。
  「どの設計ノートが Gate を通ったか」を機械が言えるようにするのは、まさに本裁定で導入する
  `GatePassage` の役割であり、実装後はそちらが正となる。

## 本記録に基づく遷移

- `SDD-DSN-010`: `draft → active`（frontmatter 更新。上記のとおり lifecycle 管理外）
- `SDD-DSN-011`: `draft → active`（同上）

要件（`SDD-FR-*`）の起票と `draft → approved` は Plan フェーズで別途行う。
