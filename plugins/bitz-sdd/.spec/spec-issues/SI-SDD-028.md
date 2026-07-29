---
id: SI-SDD-028
raised_by: bitz-flow v2 FLW-REV-002多観点レビュー（2026-07-29）
target: sdd-reviewのDesign Gate前トレーサビリティ評価をフェーズ対応にする
proposed_change_type: modify
status: open
---
- **目的**: Design Gate前の設計レビューで、まだ派生していないFR/NFR/CONと空の`implements`を
  criticalな欠落として扱わないよう、sdd-reviewのトレーサビリティ評価をSDDフェーズに対応させる。
  bitz-flow v2のFLW-REV-002では、sdd-coreの`gates.md`が「FAIL設計から要件を派生しない」
  「Design Gate後にactive docsからdraft要件を派生する」と規定している一方、consistency/business
  観点が要件→設計トレースを無条件に要求し、要件未作成をP0と判定した。指摘に従って要件を作ると
  Gate違反になり、従わないとレビューFAILを解消できない循環が生じる。
- **提案する修正**:
  1. review実行時に`review_stage`と`traceability_mode`を明示する。少なくとも
     `pre-design-gate`と`post-design-gate`を区別し、統合報告にも記録する
  2. `pre-design-gate`ではDiscovery/提案docs→Designの由来、設計間整合、未解決gapを評価し、
     要件未作成・空の`implements`自体をfindingにしない
  3. `post-design-gate`以降ではRequirements→Design→Task/実装の双方向トレースを評価する
  4. 完了済み旧要件と新設計が併存する場合、単純なworkspace全要件照合ではなく、
     レビュー対象initiative/世代へ属する成果物だけを照合する。initiative判定の正は
     SI-SDD-029の裁定へ委ねる
  5. consistency/businessの観点promptとsynthesisへ適用条件を追加し、判定根拠に
     `review_stage`、対象ID集合、N/A次元を残す
  6. skill-testerで「Designのみ」「Design+旧verified要件」「Design Gate後の新要件あり」
     の比較ケースを作り、Gate前の要件欠如をcriticalにしないことを回帰固定する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-review/SKILL.md`、
  `references/perspective-consistency.md`、`references/perspective-business.md`、
  `references/synthesis.md`、`assets/review-registry.json`、レビュー関連テスト/eval、
  必要ならsdd-reviewの後継要件。
- **確認観点**:
  - `gates.md`の「FAIL設計から派生しない」規律とレビュー改善条件が循環しないこと
  - Gate前でも既存要件と明白に矛盾する設計は検出するが、未作成要件を欠陥扱いしないこと
  - Gate後は従来どおり要件→設計→実装の欠落を検出すること
  - stage未指定時に勝手な推定でPASSせず、対象から決定できない場合は人間へ確認すること
  - review JSON/Markdownから適用したstageと対象集合を再現できること
- **影響推定・ロールバック**: `spec inspect --impact SDD-FR-060`の機械列挙は
  bitz-sddの`SDD-TSK-002` 1件。既存SDD-FR-060はdecision keyだけを規定し本問題を扱わないため、
  新規要件候補とする。レビュー判定という公開契約を変更するため軽量レーン不可、通常フロー +
  Design Gateが必要。ロールバックはstage対応prompt/registryとテストを一括revertし、従来の
  単一評価へ戻す。ただし循環問題が再発するため、未解決の間はGate前レビューで本Issueを既知制約として示す。
- **依存**: `sdd-core/references/gates.md`、SI-SDD-029（initiative/世代の識別方法）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | SDD-FR-060/061とは非重複。gates.mdとの実運用矛盾を解消する新規契約候補 |
| ガードレール抵触 | なし。人間のDesign Gate裁定を維持する |
| 影響範囲 | sdd-reviewの2観点、synthesis、registry、eval。impact機械列挙は1タスク |
| 軽量レーン適否 | 不可。レビュー判定とGate接続の公開契約を変更する |

**推薦: accept**。現状はレビュー指摘を解消する行為自体がGate違反になるため、再現可能な
プロセス欠陥である。
