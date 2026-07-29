---
id: SDD-REV-006
title: "bitz-sdd 全体の振り返り（Design 層の欠落・逆起票要件・ライフサイクル運用実績・過去レビュー指摘の消化状況）"
status: active
version: 1.0
updated: 2026-07-29
owner: claude
decision: CONDITIONAL_PASS
---

# SDD-REV-006 bitz-sdd 全体の振り返り（2026-07-29）

- **review_id**: SDD-REV-006
- **対象**: `plugins/bitz-sdd/.spec/` 全体（design / requirements / discovery / reviews / STATE）と
  実装スキル14件、および全ワークスペースのライフサイクル運用実績
- **判定**: **CONDITIONAL_PASS**
- **集計スコア**: 3.03 / 5.00（PASS ≥ 3.5 / CONDITIONAL ≥ 2.5）
- **契機**: 「他のスキルを作成するため bitz-sdd を駆け足で作ってきた。一旦振り返り、
  きちんとした設計に落とし込みたい」という方針転換（人間指示 2026-07-29）

> 本レビューは SDD-REV-005 を `SDD-REV-005.{json,md}` へ退避し、最新の全体統合判定として
> `review-synthesis.{json,md}` を上書きする（SDD-REV-004 と同じ運用）。

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 3.00 | 0.20 | 下流トレースは模範的。上流（設計→要件）が欠落し46%が逆起票 |
| operations | 3.20 | 0.27 | **レビュー指摘の消化が追跡されない**。宣言した計測項目に実装がない |
| risk | 2.33 | 0.20 | **担保が1点に集約されているのにその1点が動いていない**。前回 P1 が未解消 |
| business | 3.30 | 0.20 | Discovery の投資は健全。責務分界の未定義が拡大しつつある |
| data-integrity | 3.40 | 0.13 | 証跡機構は健全だが集約境界が未設計 |

findings: 統合前16件 → 重複排除後10件（P0: 2 / P1: 6 / P2: 1 / P3: 1）

## 総括 — 「駆け足だった」のは Discovery ではなく Design

| 層 | 実態 |
|---|---|
| Discovery | 6成果物・456行、仮説検証ゲートあり。**投資は健全で再利用できる** |
| **Design** | `domain-model.md` **無し**、`ROADMAP.md` **無し**、DSN は spec-issue 対応の個別ノート5件 |
| Requirements | 67件。うち **31件（46%）が SKILL.md からの逆起票**。対応設計を持つのは2件 |
| Review | SDD-REV-002〜005 + synthesis。**実施されるが指摘が消化されない** |
| Verify | 63 verified。機械検証つき |
| Promotion | **0件** |

形は **Discovery ✔ → Design を飛ばす → 実装から逆起票して Requirements を埋める →
spec-issue 単位の増分 → verified で止まる**。以下の指摘はほぼすべてこの一点の帰結である。

## P0 — Blocker

### SYN-001 [OPS-601] レビュー指摘の消化が追跡されず P1 が起票されないまま消えた

- **場所**: `.spec/reviews/SDD-REV-004.md` / `review-synthesis.json` の `gate_preconditions`
- **問題**: SDD-REV-004（2026-07-22）は自身の指摘（P1・mtime 精度による無音データ損失
  リスク）を「**別途 spec-issue 化を推奨**」と明記したうえで `decision: PASS` とした。しかし
  該当の spec-issue は起票されず、実装も 2026-07-29 現在まで未変更である。次のレビュー
  SDD-REV-005 はスコープが異なるため拾わず、`gate_preconditions` は空配列のままだった。
  同じ経路で SDD-REV-004 の指摘（`sdd_sync` が mutation lock に不参加、Discovery が停止）も
  未消化のまま残っている。
  **レビューは実施されても効果が消える構造になっている。**
- **なぜ P0 か**: 本レビュー自身がこの構造の中にあり、仕組みを直さなければ本レビューの指摘も
  同じ経路で消える。他の全指摘の前提条件である。
- **推奨**: P0/P1 の指摘について spec-issue への紐づけを synthesis の必須項目とし、
  未紐づけのまま PASS できないようにする。既存の `gate_preconditions` フィールドを実際に運用する。

### SYN-002 [RSK-601] 代行遷移の唯一の担保である Promotion Gate が一度も動いていない

- **場所**: 全ワークスペースの `.spec/requirements/` と `STATE.md`
- **問題**: 代行可視化経路は「裁定の真正性は機械検証されない。Promotion Gate で人間が
  decision-ref を確認する」ことを唯一の担保として設計されている（SDD-FR-145）。実測では
  bitz-sdd は63件すべて verified 止まりで **promoted 0件**、bitz-env 19件・bitz-flow 2件・
  bitz-ddd 2件も 0件。promoted 実績はルートの26件のみ。一方で代行遷移は bitz-sdd 14件・
  ルート28件まで蓄積した。
- **追跡**: SI-SDD-028（open）

## P1 — Must Fix

### SYN-003 [RVC-601 / RVC-602] Design 層が欠落し、要件の46%が実装からの逆起票である

sdd-core が定義する `.spec` 構成に対し、bitz-sdd 自身が `ROADMAP.md` と `domain-model.md` を
持たない。**構成の定義者が自らの構成を満たしていない。** 要件67件のうち31件は `origin` に
reverse-derived を持ち、設計判断の記録を伴わない。SDD-REV-004 が指摘した
「対応設計の逆リンクが一部要件にしかない」状態は現在も続き、対応設計を持つ要件は2件のみ。

**推奨**: Design 層を後付けし、逆起票31件を「契約として妥当 / 実装詳細を要件化してしまっている /
廃止すべき」に**分類**する。書き直しではなく分類とする（SYN-010 参照）。

### SYN-004 [RSK-602 / RSK-603] SDD-REV-004 の未消化指摘

SYN-001 の具体的な帰結。いずれも spec-issue 化されていない。

| 指摘 | 現状 |
|---|---|
| mtime 精度の非対称 | `sdd_sync.py` は書き込みに `st_mtime_ns`、比較に `st_mtime` を使う |
| `sdd_sync` が mutation lock に不参加 | lock 参加は grep 0件。並行実行で lost update がありうる |

### SYN-005 [OPS-602 / RVC-604] manual-check が42.5%を占めるが監視も記録形式も無い

`adoption-metrics.md` は 20% 閾値を宣言するが比率計算の実装が無く（grep 0件）、実測は
**51/120 = 42.5%** で宣言の2倍を超える。`verification.md` は実施記録の記録先も書式も
定義していないため、実施したか否かを機械も人間も判定できない。加えて SDD-FR-148 と
SDD-FR-153 が manual-check を機械検査から二重に免除しており、**検証が最も弱い領域が
最も監視されていない**。

- **追跡**: SI-SDD-029（open）

### SYN-006 [RVC-606 / RVC-605] `verification_method` と証跡の集約境界が不一致

要件は検証手段を1つ宣言するが、実際の検証は1回の実行が複数要件を覆う。証跡の
`requirements` は単なる配列で、検証手段の異なる要件を同一実行へ束ねられる。
集約境界を設計しないまま実装した結果である。**schema の利用実績が1件のうちに直せば
移行が不要**であり、時間依存のコストがある。

- **追跡**: SI-SDD-030（open）

### SYN-007 [BIZ-603] Discovery が 2026-07-12 で停止し宣言と実体が乖離している

SDD-REV-004 が指摘済みで未対応。とくに `scope.md` は sdd-git を
「bitz-flow へ移管予定」と宣言するが、**bitz-flow は 0.3.0 のプラグインとして実在し
main 上に要件2件・設計成果物15件を持つのに、sdd-git は bitz-sdd 内に残る**。
Open Question「bitz-sdd↔bitz-flow 依存境界の粒度」も未決。

> **訂正（2026-07-29）**: 初版は要件数を「19件」と記載していたが、これは並行作業中の
> worktree（`BitzSkills-wt/bitz-flow-v2`）の未コミット状態を、共有された作業ツリー越しに
> 読んだ誤りだった。main の実体は2件である。**測定値を作業ツリーから読むと、
> 並行作業の途中状態を確定値として記録してしまう** — 本訂正自体が SI-SDD-033 の実例である。
> 指摘の実質（bitz-flow は実在するのに sdd-git が未移管）は変わらない。

### SYN-008 [BIZ-604] 14スキルの責務分界が未定義のまま15個目を追加しようとしている

スキル間の責務境界を定義した設計成果物が存在しない。唯一 accepted 未着手の SI-SDD-013 は
「新 sdd-usecase スキルの責務分界を Design Gate で確定する」であり、境界の定義なしに
追加すると分界問題が15スキルへ拡大する。`scope.md` が「本格 DDD 手法は bitz-ddd の責務」と
宣言しているため、モデリングの道具として bitz-ddd を用いること自体は宣言と整合する。

- **追跡**: SI-SDD-013（accepted・未着手）

## P2

### SYN-009 [OPS-604] SDD ツールの呼び出し規約が2系統に分かれている

`scripts/spec` ラッパー経由（inspect / scaffold / status / update）と、スキル同梱スクリプトの
直接実行（`sdd_sync.py` / `docs_inspect.py` / `sdd_report.py` / `spec_verify.py`）が併存する。
ラッパーは sdd-core の4ツールすべてを必須解決する設計のため新ツールを追加できず、
SI-SDD-016 では直接実行を選ばざるを得なかった。CORE-FR-011 の改訂を伴う。

## P3

### SYN-010 保全すべき資産

設計の後付けにあたり、以下は**置き換えず照合対象として保全する**。

- **63件の verified** — 要件はタスク・テスト・実行証跡へ接続され、`spec_inspect` が
  孤児・幽霊・未参照を機械検出する。破棄すれば検証済みの状態がゼロに戻る
- **Discovery 6成果物（456行）** — 内容は具体で、bitz-ddd・bitz-env への責務委譲や
  sdd-git 移管方針を既に予見している。欠けているのは Discovery ではなく Design である
- **検証証跡の許可リスト設計** — 秘密値混入防止はガードレールと整合しており、
  manual-check の実施記録形式を新設する際も同じ制約を継承すること

## Gate 前提条件（消化するまで Design Gate / Promotion Gate を通過しない）

SYN-001 の指摘を本レビュー自身に適用し、`gate_preconditions` を実際に埋める。

| ID | 由来 | 条件 | 状態 |
|---|---|---|---|
| GP-001 | SYN-001 | レビュー指摘の spec-issue 化を機械的に追跡する仕組みを設計フェーズの対象に含める | open |
| GP-002 | SYN-004 | SDD-REV-004 の未消化指摘（mtime 精度・mutation lock 不参加）を spec-issue として起票する | **satisfied**（SI-SDD-032） |
| GP-003 | SYN-003 | Design 層を後付けする（`domain-model.md` と `ROADMAP.md` の作成、逆起票31件の分類） | open |
| GP-004 | SYN-007 | Discovery を実体へ追随させる（破棄せず改訂） | open |
| GP-005 | SYN-009 | SDD ツール呼び出し規約の統一方針を裁定する（CORE-FR-011 の改訂可否を含む） | open |

## 保留（本レビューでは決定しない）

- **bitz-sdd ↔ bitz-flow の依存境界と sdd-git 移管** — bitz-flow の discovery / design が
  並行進行中のため、決定は同プラグインの完了後の最終合わせで行う（人間裁定 2026-07-29）。
  GP-004 の Discovery 改訂でも、この境界に関する記述は据え置く。

## 破壊的変更の方針

**許容**（人間裁定 2026-07-29）。ただし設計の結論が公開契約の破壊的変更を要する場合、
bitz-ddd の `bitz-sdd>=2.0` 依存と、本リポジトリが bitz-sdd を固定版で消費している事実への
波及を、移行計画として明示すること。

## 人間への裁定依頼

この判定は推奨である。**critical finding が2件あるため PASS ではなく CONDITIONAL_PASS とした。**
SDD-REV-004 が P1 を残したまま PASS した経緯（SYN-001）を踏まえ、本レビューでは
`gate_preconditions` を空にせず5件を明示した。GP-001〜GP-005 の消化前に Design Gate を
通さないことを推奨する。

## 指摘の追跡先（GP-001 の規律を本レビュー自身へ先行適用）

SDD-REV-004 が「spec-issue 化を推奨」と書いたまま起票されなかった経緯を繰り返さないため、
本レビューは判定と同時にすべての P0/P1 へ追跡先を割り当てた。**未紐づけの P0/P1 はゼロ**。

| finding | 優先度 | 追跡先 |
|---|---|---|
| SYN-001 | P0 | SI-SDD-031（本レビューで新規起票） |
| SYN-002 | P0 | SI-SDD-028 |
| SYN-003 | P1 | 本レビューの GP-003 |
| SYN-004 | P1 | SI-SDD-032（本レビューで新規起票） |
| SYN-005 | P1 | SI-SDD-029 |
| SYN-006 | P1 | SI-SDD-030 |
| SYN-007 | P1 | 本レビューの GP-004 |
| SYN-008 | P1 | SI-SDD-013 |
| SYN-009 | P2 | SI-CORE-038（本レビューで新規起票） |

SYN-003 / 007 は Design 層の後付けと Discovery 改訂そのものであり、独立した spec-issue では
なく本レビューの Gate 前提条件として追跡する。重複起票を避けるための意図的な選択である。

起票済みの spec-issue（SI-SDD-013 / 028 / 029 / 030 / 031 / 032、SI-CORE-038）は
いずれも人間裁定待ちである。
