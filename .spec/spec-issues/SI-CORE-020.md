---
id: SI-CORE-020
raised_by: PR #30/#31 スタック運用での自動クローズ事故（2026-07-13 セッション）
target: plugins/bitz-sdd/skills/sdd-git（未マージ依存時のブランチ運用の記述不足）
proposed_change_type: doc
status: accepted
---
- **目的**: 着手対象のタスク／要件が「まだ main にマージされていない別 PR」に依存する場合の
  ブランチ運用を sdd-git に明文化する。現状フローは feature ブランチを main から切り squash merge する
  フラットな前提のみで、**未マージ依存の扱い（前提を先に land するか、スタックするか）を規定していない**。
  この記述不在が、2026-07-13 セッションでの独自スタックPR運用と `--delete-branch` による下段 PR
  自動クローズ事故の遠因となった。
- **背景（実事故）**: SI-CORE-012 実装 PR を、未マージの裁定 PR（`docs/si-core-006-019-accept`）の
  ブランチを base にスタックさせた。上段（裁定 PR）を `gh pr merge --delete-branch` した際に base
  ブランチが消え、GitHub 仕様により下段 PR（#31）が retarget されず自動クローズされた。復旧のため
  リベース＋新 PR（#32）再作成が必要になった。規定フロー（main 分岐＋squash）に忠実なら、
  「前提 PR を先に main へ land → 更新後 main から分岐」で事故は発生しなかった。
- **提案する修正**:
  1. sdd-git `references/issue-driven-flow.md`（または SKILL.md のフロー選択節）に
     **「未マージ依存の原則」**を1節追加する。既定は **「依存先 PR を先に main へ land し、
     更新後の main からブランチを切る（スタックしない）」**。1 PR = main 分岐 = squash の前提を崩さない。
  2. どうしてもスタックが必要な例外時の注意を併記する:
     - 下段 PR の base ブランチは上段マージ時に **`--delete-branch` しない**（下段が巻き添えで close される）
     - 上段マージ後は下段を **main へ retarget（リベース）** してから独立にマージする
  3. sdd-implement の depends_on 記述と整合する形で「タスクの depends_on が
     未マージ成果物に及ぶ場合は着手前に land を待つ」旨をクロス参照する。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-git/references/issue-driven-flow.md`、
  必要なら `plugins/bitz-sdd/skills/sdd-git/SKILL.md`、bitz-sdd マニフェスト bump。
- **確認観点**:
  - ドキュメント追記のみで既存フローの挙動を変えないこと（規定の追加であって変更でない）
  - release_check / spec_inspect PASS
  - 記述が「既定＝land 優先／例外＝スタック時の delete-branch 禁止」を明確に分けていること
- **影響推定・ロールバック**: ナラティブ文書への追記のみ。単独 revert 可能。
- **依存**: なし（軽量レーン適否は裁定時に人間が判断。契約〈公開 API・スキーマ・frontmatter 書式〉には触れない）。
- **実装完了（2026-07-13）**: 軽量レーン（doc 記載漏れ修正のため要件・タスクは起票せず）。
  `sdd-git/references/issue-driven-flow.md` に「未マージ依存の原則」節を追加、sdd-git 0.2.0 / bitz-sdd bump。
