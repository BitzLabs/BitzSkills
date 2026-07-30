# 派生とゲート（Discovery / Design / Promotion）

## docs/ → .spec/ の派生（半自動）

- planエージェントが docs/ の該当節から requirements/ の **draft** と specs/<feature>/ の骨子を生成する
- **派生元にできるのは `status: active` の docs 文書のみ**。proposed ドラフトからは派生しない（先に Design Gate で active 化する）
- 生成物の frontmatter に `derived_from: docs/…@<コミットSHA>` を必ず記録
- draft → approved は人間専権。**生成は速く、統制は保つ** — 派生の自動化と契約の承認を分離する設計

### 上流成果物 → 要件の派生対応（目安）

| docs/ 側の成果物（active 化済み） | 派生する要件の型と verification_method |
|---|---|
| success-metrics のガードレール指標（`sdd-discovery`） | NFR（benchmark / load-test、数値必須） |
| non-goals / constraints（`sdd-discovery`） | CON |
| ドメインストーリーのハッピーパス（bitz-ddd の `ddd-story`） | FR（1 Activity ≒ 1 EARS 節の粒度） |
| 軽量ドメインスケッチの主要ユースケース（bitz-ddd 未導入時の `sdd-design`） | FR（1 ユースケース ≒ 1 EARS 節の粒度） |
| public-api のエンドポイント契約（`sdd-design`） | FR（example-test / pbt） |
| SLO・エラーバジェット（`sdd-ops`） | NFR（benchmark / load-test、数値必須） |
| security-model の統制（`sdd-ops`） | NFR（sast / dep-audit） |

## ゲート一覧 — 人間裁定点は3つ

いずれもエージェントは**証跡とドラフトを揃えてチェックリスト形式で提示するだけ**。自分でチェックを付けて通過させない。
フェーズ語彙（`map / discovery / design / plan / execute / verify / done` の7語）は
`spec_status.py` の `PHASE_CODES` が正（SDD-FR-136）。ゲートとフェーズの対応:
<!-- phase-vocabulary: map, discovery, design, plan, execute, verify, done -->
<!-- ↑ 機械検証用マーカー。上の散文リストと同一で、release_check.py が PHASE_CODES との一致を検査する（SDD-FR-140）。語を増減するときは PHASE_CODES・散文リスト・本マーカーを同時に更新する。 -->
Discovery Gate = Discovery の出口（Design へ）、Design Gate = Design の出口（Plan へ）、
Promotion Gate = Done の出口（promoted へ）。

### 1. Discovery Gate（Map / Discovery の出口）

`sdd-discovery` の仮説検証（Go / No-Go / Pivot）。証跡は `.spec/discovery/assumptions.md`。No-Go / Pivot のまま Design 以降のフェーズに進まない。

### 2. Design Gate（proposed → active）

Design フェーズの出口。docs/ の proposed ドラフト（`00_はじめに` / `01_システム仕様` / `02_ユースケース` / `03_設計仕様`）を人間が active 化する裁定点。`sdd-review` の統合判定（PASS / CONDITIONAL_PASS / FAIL）とレポートを添えて提示する。CONDITIONAL_PASS の条件リストは STATE.md で消化を追跡し、未消化のまま該当節から要件を派生しない。FAIL の設計から派生を始めない。

### 3. Promotion Gate（verified → promoted）

Done フェーズ（全検証 green）の出口であり、feature 完了時の唯一の逆流点。planエージェントがドラフト一式を用意し、人間が以下のチェックリストで裁定する:

1. □ docs/ 更新ドラフトの承認（ARCHITECTURE 変更・ADR 追記・glossary 新語 — proposed で用意し、承認で active 化）
2. □ LESSONS_LEARNED 候補の取捨選択
3. □ tombstone テストの削除可否判定（後継テスト green を確認）
4. □ stale マークゼロの確認（spec_inspect.py レポートの目視）
5. □ 代行遷移（agent-proxy-unverified）の decision-ref を人間が確認
   （STATE.md の代行実行行と参照先の裁定記録を突き合わせ、裁定の真正性を目視で担保する。
   経路別件数は spec_status.py / sdd_report.py が集計する — SDD-FR-145）
6. □ （任意）docs/ 更新ドラフトが大きい場合は `sdd-review` を実行し判定を添付
7. □ specs/<feature>/ を `.spec/archive/<date>-<feature>/` へアーカイブ
8. □ **GatePassage を起票し、昇格を `--gate-passage` で紐づける**（SDD-FR-155 / SDD-FR-157）

### Gate 通過の記録（GatePassage）

手順としてのチェックリストだけでは「Gate が一度も実行されていない」ことを機械が言えない。
通過そのものを `.spec/gates/<NS>-GATE-NNN.md` の**不変記録**として残す:

```bash
python3 scripts/spec scaffold <ws> gate --prefix <NS>-GATE --gate promotion \
    --arbiter <裁定者> --scope "<ID>,<ID>,..." --decision-ref <裁定記録の所在>
python3 scripts/spec update <ws> <ID> <ID> ... --to promoted --gate-passage <NS>-GATE-NNN \
    --on-behalf-of <人間> --decision-ref <裁定記録の所在> --actor <実行者>
```

- frontmatter の必須項目は `id` / `gate`（`discovery` | `design` | `promotion`）/ `date` /
  `arbiter` / `scope` / `confirmed_decision_refs` / `checklist_ref`。`spec inspect` が検査する
- 裁定の理由と経緯は `.spec/reports/decision-*.md` が持つ。GatePassage は
  `confirmed_decision_refs` でそれを参照し**二重管理しない**
- `scope` の ID と `confirmed_decision_refs` の参照先は実在検査の対象（幽霊参照を許さない）
- Discovery / Design Gate でも同じ形式で記録できる（`--gate discovery` / `--gate design`）

Gate を自動化しない理由: ここが緩むと docs/ が「エージェントの作業ログ置き場」に劣化し、永続層の信頼が死ぬ。
GatePassage は裁定を自動化するものではなく、**人間が裁定した事実を機械可読に残す**ためのもの。
