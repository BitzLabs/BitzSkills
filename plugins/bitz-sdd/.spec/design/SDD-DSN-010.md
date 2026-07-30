---
id: SDD-DSN-010
title: "GatePassage — Gate 通過の成果物化と未検分な代行遷移の滞留可視化"
status: active
version: 1.1
updated: 2026-07-30
owner: hide
implements: 
origin: SI-SDD-028
---

# SDD-DSN-010 GatePassage — Gate 通過の成果物化と未検分な代行遷移の滞留可視化

Design Gate 裁定2（2026-07-29「導入する」）の設計。ROADMAP フェーズ3 順序6。
SDD-DSN-011（ReviewFinding）と並行実装可能。

- **背景 / 課題**:
  - 代行可視化経路（`--on-behalf-of`）は「裁定の真正性は機械検証されない。Promotion Gate で
    人間が decision-ref を確認する」ことを**唯一の担保**として設計されている（SDD-FR-145）。
    その1点が動作していない。実測（2026-07-30）で bitz-sdd は要件67件中 verified 63・
    **promoted 0**、代行遷移は18件。promoted 実績があるのはルートの26件だけである。
  - SDD-DSN-009 の Pass 2 で、**Gate 通過を表す成果物をどの機能も生成していない**ことが判明した
    （問題(2)）。手順は `gates.md` に定義されているのに実体が無く、「Promotion Gate が一度も
    実行されていない」ことを機械が言えない。
  - 一方で判定材料は揃っている。STATE の構造化 event は `schema_version: 2` で
    `artifact_id` / `old` / `new` / `timestamp` / `provenance{kind, actor, on_behalf_of, decision_ref}`
    を持ち、`spec_status.py:74` が既に経路別件数を集計している。**足りないのは「検分した」側の記録**だけである。

- **設計判断**:
  1. **`GatePassage` を独立成果物として導入する**。配置は `.spec/gates/<NS>-GATE-NNN.md`。
     frontmatter に機械可読属性を持たせ、本文は薄くする。裁定の理由と経緯は既存の
     `.spec/reports/decision-*.md` にあるため、`confirmed_decision_refs` で参照し**二重管理しない**。

     ```yaml
     id: SDD-GATE-001
     gate: promotion            # discovery | design | promotion
     date: 2026-07-30
     arbiter: hide              # 裁定者（人間）
     scope: [SDD-FR-001, SDD-FR-010, ...]   # 対象成果物 ID の明示列挙
     confirmed_decision_refs:   # この Gate で人間が実際に確認した裁定記録
       - .spec/reports/decision-2026-07-29-design-gate.md
     checklist_ref: skills/sdd-core/references/gates.md#3-promotion-gateverified--promoted
     ```

  2. **検分の単位は要件ではなく `decision_ref` とする**（SI-SDD-028 提案1 の定義を精緻化）。
     提案1 の原文は「対象要件が promoted に達していないもの」を滞留とするが、この定義では
     判定できない代行遷移がある。**代行遷移は spec-issue の `open → accepted` にも起きており**
     （実測: bitz-sdd の代行18件の多くがこれ）、spec-issue は `promoted` 状態を持たないため
     永久に滞留扱いになってしまう。
     - **未検分の代行遷移** ＝ STATE event のうち `provenance.kind == "agent-proxy-unverified"` で、
       その `provenance.decision_ref` が**どの GatePassage の `confirmed_decision_refs` にも
       現れない**もの。
     - 1つの裁定記録が複数の遷移を束ねるため、検分の単位を裁定記録に置くほうが人間の作業とも一致する。

  3. **`verified → promoted` 遷移は `GatePassage` の参照を必須とする**（提案3 の答え。
     現状 promoted 遷移そのものに確認記録の欄がない）。
     - `spec update <ws> <IDs...> --to promoted --gate-passage <GATE-ID>`。未指定なら拒否する。
     - **Gate の実行単位は「1 GatePassage = 1回の Gate 実行」**とし、対象は ID の集合を
       `scope` に明示列挙する。feature 単位に固定しない — bitz-sdd 自身のような
       reverse-derived ワークスペースには feature 境界が無く、63件はどの feature にも紐づかない。
       集合を明示列挙する形なら feature 単位でも一括でも表現できる。
     - **後方互換**: 本規律は導入後の遷移にのみ適用し、既存の promoted 26件へ遡及しない
       （lifecycle.md「本規律は導入後の遷移に適用し、既存の verified 要件へ証跡の遡及追加を
       要求しない」の前例に倣う）。

  4. **滞留を可視化する**（提案1・2）。
     - `spec_status.py` の JSON へ**加算のみ**で追加する:
       `unreviewed_proxy_decisions: {count, oldest_age_days, decision_refs: [...]}`。
       `phase_code` と同じく公開契約なので既存キーは変えない。
     - `next_actions` に「未検分の代行遷移が N 件（最古 M 日）」を追加する。
       **滞留ゼロのワークスペースでは出力しない**（確認観点「滞留ゼロでノイズが出ないこと」）。
     - `adoption-metrics.md` に計測項目として「未検分の代行遷移件数」「最古の滞留日数」を定義する。
       ただし **閾値を宣言するなら同時に機械集計を実装する**ことを条件とする —
       `manual-check` 比率 20% が宣言だけされて実装が無かった失敗（SI-SDD-029）を繰り返さない。

  5. **`lifecycle.md` に「verified は完了ではない」を明記する**（提案4）。状態遷移表の
     `verified → promoted` 行に、verified のまま滞留し続けることが正常状態ではないことを書く。
     現行記述は verified を終端のように読ませており、滞留を追認している。

- **契約境界**:
  | 種別 | 対象 | 性質 |
  |---|---|---|
  | 新設 | `.spec/gates/` ディレクトリ（`.spec` スキーマ = 公開契約） | 加法的 |
  | 変更 | `spec_update` CLI に `--gate-passage`（promoted 遷移でのみ必須） | 加法的（既存遷移は無影響） |
  | 加算 | `spec_status` JSON キー `unreviewed_proxy_decisions` | 加算のみ |
  | 追加 | `spec_scaffold` に `gate` 種別 | 加法的 |
  | **不変** | **STATE event の `schema_version: 2`** | 変更しない |

  最後の1点が重要である。GatePassage を**独立成果物**にすることで event schema に触れずに済み、
  順序6 を加法的に保てる。event schema へ検分フラグを足す設計にすると、証跡 schema を拡張する
  順序8（裁定1 + 裁定5、破壊的）と同じ成果物を奪い合い、順序6 が破壊的変更に格上げされてしまう。

- **代替案と却下理由**:
  1. **既存の `decision-*.md` を GatePassage として流用する** — 却下。自由文のナラティブであり
     機械可読でない。frontmatter を後付けすると既存6件の書式変更を伴い加法的でなくなる。
     GatePassage から `confirmed_decision_refs` で参照する形なら二重管理にならない。
  2. **STATE event に `gate_passage` フィールドを足す** — 却下。上記「契約境界」の理由により
     順序8 と衝突し、順序6 の加法性が失われる。
  3. **検分の単位を「要件が promoted か」にする**（提案1 の原文どおり） — 却下。設計判断2 の理由。
     spec-issue の代行遷移を永久に滞留扱いにしてしまう。
  4. **GatePassage を `requirements/` に置く** — 却下。ライフサイクルが違う。GatePassage は
     status 遷移を持たない不変の記録であり、種別ごとに集約を分ける裁定4 の方向と逆行する。

- **影響範囲・ロールバック**:
  - 影響: `sdd-core`（`lifecycle.md` / `gates.md` / `adoption-metrics.md` / `spec_update.py` /
    `spec_status.py` / `spec_scaffold.py`）、`sdd-report`、関連テスト、bitz-sdd マニフェスト。
  - 他プラグインへの波及: promoted 遷移を使うワークスペース（ルート・bitz-env・bitz-flow・bitz-ddd）は
    以後 GatePassage が必要になる。**導入後の遷移のみ対象**のため既存の promoted は無傷。
  - ロールバック: `--gate-passage` の必須化を外せば従来動作に戻る。`.spec/gates/` が残っても
    他の検査には影響しない。滞留の可視化はセクション単位で revert できる。

- **実装順序**:
  1. `.spec/gates/` スキーマと `spec_scaffold` の `gate` 種別（成果物を作れるようにする）
  2. `spec_status` の滞留集計と `next_actions`（**現状の18件が可視化される**）
  3. `spec_update --gate-passage` の必須化と `lifecycle.md` / `gates.md` の改訂
  4. `adoption-metrics.md` の計測項目（機械集計とセット）

  2 までで「滞留が見える」状態になり、3 で「今後は検分なしに promoted へ行けない」が成立する。

- **Design Gate 入力（裁定を要する点）**:
  | # | 裁定点 | 選択肢 | 推奨 |
  |---|---|---|---|
  | D1 | `.spec/gates/` の新設 | 新設する / `reports/` に同居させる | **新設**（機械可読性と責務の分離） |
  | D2 | 検分の単位 | `decision_ref` / 対象要件の promoted 到達 | **`decision_ref`**（spec-issue の代行遷移を判定できる） |
  | D3 | promoted 遷移での GatePassage | 必須 / 任意（警告のみ） | **必須**（担保が1点しかないため） |
  | D4 | 滞留の閾値宣言 | 宣言する（機械集計とセット） / 件数の可視化のみ | **可視化のみ先行**（SI-SDD-029 の轍を踏まない） |

- **Design Gate 裁定**: **2026-07-30・対話裁定で D1〜D4 すべて裁定済み**。裁定者 hide、
  裁定記録は `.spec/reports/decision-2026-07-30-design-gate-order6.md`。

  | # | 裁定 | 推奨との異同 |
  |---|---|---|
  | D1 | `.spec/gates/` を新設する | 推奨どおり |
  | D2 | 検分の単位は `decision_ref` | 推奨どおり（SI-SDD-028 提案1 の定義を上書き） |
  | D3 | promoted 遷移で `--gate-passage` を必須にする | 推奨どおり |
  | D4 | 閾値は宣言せず可視化のみ先行する | 推奨どおり |

  本ノートは裁定を受けて `draft → active`。実装は要件化（Plan フェーズ）から開始する。
