---
id: SI-SDD-007
raised_by: 開発フロー振り返り（2026-07-18 セッション、SI-CORE-007 実装サイクルの実地観察）
target: plugins/bitz-sdd/skills/sdd-implement（accepted spec-issue 着手時の前提再検証ステップの不在)
proposed_change_type: modify
status: open
---
- **目的**: accepted のまま在庫化した spec-issue は、実装着手時点でリポジトリの前提が
  起票時から変わっていることがある（実例: SI-CORE-007 は起票時「2マニフェスト同値」だったが、
  着手時には SI-CORE-024 で Codex が加わり3マニフェストが正になっていた）。今回は要件化時に
  エージェントが暗黙に吸収したが、この再検証は規律として明文化されておらず、見落とすと
  古い前提のまま実装される。
- **提案する修正**:
  1. sdd-implement（または sdd-core references/lifecycle.md）の実装着手手順に
     「**起票時前提の再検証**」を1ステップ追加する: accepted spec-issue に着手する際、
     本文の対象ファイル・件数・書式などの前提が現状と一致するかを確認し、
     乖離があれば要件化時に補正して要件の Revision History に乖離内容と補正理由を明記する
  2. 乖離が提案の趣旨自体を変える規模なら、実装に進まず spec-issue を再裁定
     （人間へ差し戻し）するルートも合わせて規定する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-implement/SKILL.md`（または
  `skills/sdd-core/references/lifecycle.md`）、bitz-sdd マニフェスト bump。
- **確認観点**: 追記が1ステップの明文化に留まり、既存の実装規律（契約保護・境界厳守）と
  矛盾しないこと。release_check / spec_inspect PASS。
- **影響推定・ロールバック**: ドキュメント追記のみ。該当節の revert で戻る。
- **依存**: なし。
