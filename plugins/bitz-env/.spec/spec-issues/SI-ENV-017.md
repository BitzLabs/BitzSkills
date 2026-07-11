---
id: SI-ENV-017
raised_by: skill-evaluator
target: plugins/bitz-env/skills/env-doctor/SKILL.md（協調構成の診断項目節）
proposed_change_type: refine
status: open
---
- **矛盾/曖昧の内容**: env-doctor の協調構成診断（レジストリ登録済みアダプタの実体確認）には、
  「実体が確認できない」場合の深刻度分類（FAIL とするか WARN とするか）の基準が
  SKILL.md 本文に明文化されていない。evals/env-doctor/runs/02（TC-01・スキルあり）では、
  インストール済みプラグイン一覧を取得する手段がテスト環境に無いことを理由に、実体の無い
  phantom アダプタ（bitz-collab-ghost）を FAIL でなく WARN として報告した
  （`runs/02/diagnosis.md` 25〜28行目、`runs/02/log.md` 22〜23行目）。この判断自体は
  一貫した理由付けがあり誤りとは言えないが、「実体なしと確定できる場合」と
  「確認手段が無く確認不能な場合」を区別する基準が SKILL.md に無いため、実行環境
  （プラグイン一覧を取得できるか否か）によって同じ入力に対する深刻度分類が
  実行のたびに揺れる可能性がある。詳細根拠: `evals/env-doctor/report.md` の
  「TC-01: ズレ注入と診断」節の考察部分。
- **提案する修正**: env-doctor の協調構成診断項目に、以下の分岐基準を追記する。
  (a) インストール済みプラグイン一覧等の確認手段が利用可能で、かつ実体が存在しないと
      確定できる場合は FAIL として報告する。
  (b) 確認手段が利用できず実体の有無を確定できない場合は WARN とし、
      「確認不能である」旨と、確認可能な環境（本体環境）での再確認を促す文言を
      診断結果に明記する。
  これにより、同一の入力（phantom アダプタの登録）に対して実行環境差だけで
  FAIL/WARN が揺れる状態を解消し、分類理由が診断結果から常に読み取れるようにする。
- **影響推定**: `plugins/bitz-env/skills/env-doctor/SKILL.md` の協調構成診断項目の記述追加
  （数行程度）。診断ロジック自体（実体確認の実行手段）は変更しない。既存テストケース
  TC-01（`evals/env-doctor/cases.md`）のアサーションは現行のまま合格するが、
  分類基準を検証する新アサーション追加を本レポートで別途提案している
  （`evals/env-doctor/report.md` の「テストケース自体への提案」節）。
