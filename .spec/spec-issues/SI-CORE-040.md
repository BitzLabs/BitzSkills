---
id: SI-CORE-040
raised_by: bitz-quality v1.0.0 QA評価
target: bitz-quality / bitz-sdd V4 / bitz-flow V2 のQA責務境界と公開接続契約
proposed_change_type: modify
status: open
github_issue: https://github.com/BitzLabs/BitzSkills/issues/267
---
- **目的**: bitz-quality v1.0.0が持つ品質判定・トレース・ゲート機能を、bitz-sdd V4と
  bitz-flow V2の公開契約へ二重管理なく接続する。評価、強制、仕様status・証跡SSOTの所有者を
  分離し、「qualityではPASSだがSDDでは未検証」のような矛盾を防ぐ。
- **提案する修正**:
  1. bitz-qualityをQA providerと位置づけ、version付き`quality-result@1`を設計する。
  2. bitz-sdd V4はquality結果の受入portを持つが、検証判定を`sdd-test`、要件status・
     GatePassage・ReviewFindingを`sdd-core`、canonical evidenceを`.spec/verification/`に保つ。
  3. bitz-flow V2はquality結果をPR/check判断へ入力し、Git/PRのenforceと副作用を所有する。
  4. adapterはFlow V2 Promotion GateとSDD V4公開port確定後に実装し、それ以前は互換性を
     `planned / contract pending`と明示する。
- **対象ファイル**: `plugins/bitz-quality/.spec/ROADMAP.md`、
  `plugins/bitz-sdd/.spec/ROADMAP.md`、`plugins/bitz-flow/.spec/ROADMAP.md`。
  裁定後は各workspaceのrequirements/design、bitz-qualityのmanifest・skills・contract testsへ波及する。
- **確認観点**: `quality-result@1`の閉集合schema、target SHA・tool/rule version・evidence digest、
  PASS/FAIL/STALE/UNKNOWNの写像、finding重複排除と`tracked_by`、provider不在時の縮退、
  atomic write・lock・移行互換、3プラットフォームcanary。
- **影響推定・ロールバック**: 公開APIと`.spec`証跡契約に関わるため軽量レーン不可。
  通常フローとDesign Gateを必須とする。adapterは加法的に導入し、既定化前は現行v1経路を維持する。
  問題時はadapterのみ無効化し、SDD/Flowのcanonical stateを巻き戻さない。
- **依存**: bitz-flow V2 Promotion Gate、bitz-sdd V4 Charter/API設計、SI-SDD-029/030/031。
- **推薦**: **accept**。ただし本issueでは責務境界と順序だけを裁定し、schema詳細・実装要件は
  3workspaceへ1関心事ずつ委託して個別のDesign Gateを通す。
