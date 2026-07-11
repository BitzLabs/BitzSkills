---
id: SI-ENV-014
raised_by: skill-evaluator（evals/env-orchestration/report.md TC-01 節・改善提案1）
target: plugins/bitz-env/skills/env-orchestration/SKILL.md（パターン選択の決定木）
proposed_change_type: bump
status: accepted
---
- **矛盾/曖昧の内容**: 「パターン選択の決定木」の1番目の枝「手順が明確な定型作業（修正・
  テスト実行・整理・一括更新）→【委譲型】worker へ」と、2番目の枝「量産・長文読解・Web検索
  など外部エージェントの得意領域→【委譲型】アダプタの delegate 役割へ」は、入力の性質に
  よって両方に該当しうる（例: evals/env-orchestration/cases.md TC-01「30ファイルの API
  移行」は、手順は定型的だが件数の規模ゆえに量産系にも見える）。決定木には両枝に該当する
  場合の優先順位・切り分け基準が無い。
  実際に evals/env-orchestration/runs/06/answer.md（TC-01 スキルあり実行）では、実行者が
  「手順が明確な定型作業でもあるが、規模的に外部アダプタの delegate 役割が適合」と自ら
  留保しながらアダプタ経由を選択しており（同ファイル10-14行目）、決定木だけでは一意に
  判定できないことが確認できる。モデル・実行者が変われば worker 委譲とアダプタ委譲とで
  判断が割れるおそれがある。
- **提案する修正**: 決定木に、両枝へ該当しうる場合の判定基準を追記する。特定ケースの
  数値（例:「30ファイル以上」）をそのまま条件に埋め込むのではなく、一般化した基準
  （例:「アダプタの能力宣言にある break-even 目安と照合し、上回ればアダプタ delegate を
  優先。目安が無ければ worker を既定とする」）を collab-contract.md の能力宣言（break-even
  フィールド）と接続する形で記述することを推奨する。
- **影響推定**: SKILL.md「パターン選択の決定木」節の記述追加（軽微・後方互換）。
  collab-contract.md の break-even フィールドとの参照関係が明示されるため、
  ENV-FR-005/006 の記述と整合するか確認が必要。
- **裁定記録**: 2026-07-12 人間裁定（チャット指示「highの3件について進めましょう」）により accepted。提案どおり反映する。
