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

### 1. Discovery Gate（Map/Discuss の出口）

`sdd-discovery` の仮説検証（Go / No-Go / Pivot）。証跡は `.spec/discovery/assumptions.md`。No-Go / Pivot のまま Plan フェーズに進まない。

### 2. Design Gate（proposed → active）

docs/ の proposed ドラフト（`00_はじめに` / `01_システム仕様` / `02_ユースケース` / `03_設計仕様`）を人間が active 化する裁定点。`sdd-review` の統合判定（PASS / CONDITIONAL_PASS / FAIL）とレポートを添えて提示する。CONDITIONAL_PASS の条件リストは STATE.md で消化を追跡し、未消化のまま該当節から要件を派生しない。FAIL の設計から派生を始めない。

### 3. Promotion Gate（verified → promoted）

feature 完了時の唯一の逆流点。planエージェントがドラフト一式を用意し、人間が以下のチェックリストで裁定する:

1. □ docs/ 更新ドラフトの承認（ARCHITECTURE 変更・ADR 追記・glossary 新語 — proposed で用意し、承認で active 化）
2. □ LESSONS_LEARNED 候補の取捨選択
3. □ tombstone テストの削除可否判定（後継テスト green を確認）
4. □ stale マークゼロの確認（spec_inspect.py レポートの目視）
5. □ （任意）docs/ 更新ドラフトが大きい場合は `sdd-review` を実行し判定を添付
6. □ specs/<feature>/ を `.spec/archive/<date>-<feature>/` へアーカイブ

Gate を自動化しない理由: ここが緩むと docs/ が「エージェントの作業ログ置き場」に劣化し、永続層の信頼が死ぬ。
