---
id: SI-ENV-016
raised_by: skill-evaluator（evals/env-orchestration/report.md TC-04 節・改善提案3）
target: plugins/bitz-env/skills/env-orchestration/SKILL.md（共通の運用ルール）+
  references/collab-contract.md（3. 報告形式（DIGEST）と検収）
proposed_change_type: bump
status: open
---
- **矛盾/曖昧の内容**: 「DIGEST のみに依存しない客観的検収」（共通の運用ルール）は
  中心が `git diff` / `git status` 等を自ら取得して確認することを求めるが、(1) 委譲先の
  作業対象が git 管理外の場合の代替検収手段、(2) DIGEST が検証の実出力を含まない
  契約違反（collab-contract.md 3節「『成功しました』だけの報告は契約違反」）だった場合に
  中心が取るべき具体的な是正アクション、のいずれも定義されていない。「差し戻す」という
  結論は書かれているが、実出力が最初から提示されない場合にどう対応するかは書かれていない。
  この空白は evals/env-orchestration/runs/09（TC-04 スキルあり実行）の検収でも、実行者が
  「テスト実行ログの提示を別途求める必要がある」と自らの判断で補って対応しており
  （runs/09/answer.md「検収結果」節）、SKILL.md 本文に明記された手順ではない。
  さらに評価時に runs/04, runs/09 の sandbox を直接確認したところ、テスト用の作業対象自体に
  `.git` が存在しないことが判明しており（.git 不在、`git rev-parse --show-toplevel` は
  リポジトリ外を指す）、git 管理外の対象に対する検収手順が定義されていない現状の実務上の
  リスクを裏付ける状況証拠となっている（evals/env-orchestration/report.md TC-04 節の
  evidence-quality 注記を参照）。
- **提案する修正**: 「共通の運用ルール」に以下を追記する。
  (a) 対象が git 管理外の場合の代替検収手段（例: 変更前バックアップとのファイル比較、
  タイムスタンプ・チェックサム比較、変更前に git init を案内する）。
  (b) DIGEST が検証の実出力を含まない契約違反の場合の定型対応（受理せず実出力の提示を
  要求し、提示されるまで先に進めない）。
  collab-contract.md 3節にも対応する記述を bump する。
- **影響推定**: SKILL.md「共通の運用ルール」節・collab-contract.md 3節の記述追加
  （軽微・後方互換）。ENV-FR-005 の受入基準に検収手段の網羅性が影響する可能性がある。
