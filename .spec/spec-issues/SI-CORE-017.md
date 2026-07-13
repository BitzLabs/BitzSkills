---
id: SI-CORE-017
raised_by: プロジェクト改修計画 追加要望（2026-07-12 ユーザー提案: sdd-issue 新設）
target: plugins/bitz-sdd/skills/sdd-issue（新設。要望インテーク→予備判定→SI 起票）
proposed_change_type: new
status: accepted
---
- **目的**: ばらばらに届く要望を整理し、可否の**予備判定**を付けて spec-issue に登録する
  インテークスキル sdd-issue を新設する。現状の起票は sdd-core の軽量レーン節の
  自由記述運用で、要望の分割・重複チェック・裁定材料の提示が定型化されていない。
- **提案する修正**:
  1. `plugins/bitz-sdd/skills/sdd-issue/` を新設する。フロー:
     ①要望の整理（1要望 = 1 SI に分割。分割原則は改修計画の ISSUE 分割原則を再利用）→
     ②重複チェック（既存 SI・要件と突合。spec_status.py の JSON 出力を利用）→
     ③可否の予備判定（判定軸: 既存要件との矛盾、ガードレール抵触、影響範囲
     spec_inspect --impact、軽量レーン適否）→ ④委託先ワークスペース判定
     （ルート/サブ。SI-CORE-015 の origin / delegated_to を設定）→
     ⑤spec_scaffold.py（SI-CORE-012）で採番・起票 → ⑥裁定材料の提示
     （accept / reject の推薦と根拠を本文に記載）
  2. **権限分離の維持**: 本スキルが行うのは予備判定と推薦まで。status は常に open で
     起票し、accepted / rejected 化（裁定）は人間のみ。「可否を判定し登録する」の
     「判定」は推薦であることを SKILL.md に明記する（sdd-core 憲法4と整合）
  3. sdd-core の管轄記述（「要件の変更・廃止・番号管理は sdd-core」）との棲み分けを追記:
     規律・ライフサイクルの正は sdd-core のまま、sdd-issue はインテーク運用フローを担う
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-issue/SKILL.md`（新規）、
  sdd-core SKILL.md（軽量レーン節からの参照・棲み分け追記）、bitz-sdd マニフェスト bump。
- **確認観点**:
  - 起票された SI が spec_inspect PASS すること（scaffold 経由なので書式互換）
  - 本スキル経由で accepted 化ができないこと（spec_update.py の --by-human 強制が効く）
  - description が sdd-core（「要件」「spec」）と過剰競合しないこと（skill-tester で発動テスト）
- **影響推定・ロールバック**: スキル追加と参照追記のみ。フォルダ削除 + 追記 revert で戻る。
- **依存**: SI-CORE-012（spec_scaffold / spec_update）、SI-CORE-015（委託フィールド）、
  SI-CORE-016（重複チェックで spec_status.py の集計を共用）。
