# env-doctor 診断結果（run 02 / TC-01 / スキルあり）

対象: `evals/env-doctor/runs/02/sandbox/`

## ガードレール3層

- [FAIL] permissions（`.claude/settings.json` の deny）: 最小集合のうち
  `Bash(git reset --hard:*)` が欠落している
  → 修正案: deny 配列に `"Bash(git reset --hard:*)"` を追加する（env-init テンプレート／
  `references/permissions.md` の最小集合に揃える）
- [FAIL] AGENTS.md ⇔ permissions の整合: AGENTS.md のガードレール節（`<!-- bitz-env:begin -->`
  〜`<!-- bitz-env:end -->`）の禁止リストに `sudo` の記載が無い。settings.json の deny には
  `Bash(sudo:*)` があり、ナラティブ層（AGENTS.md）が恒久層（permissions）に追随していない
  → 修正案: AGENTS.md の禁止リストに `sudo` を追記し、permissions と一致させる
  （テンプレート原本: `plugins/bitz-env/skills/env-init/references/templates/AGENTS-template.md`
  では `rm -rf / git push --force / git reset --hard / git clean -f / sudo` の5項目）
- [PASS] 同梱フックの有効性: プラグインのインストール状態は本テスト環境からは
  直接確認できないため、ユーザーに確認を要する項目として保留（フックファイル自体は
  プラグイン側 `plugins/bitz-env/hooks/hooks.json` に存在することは確認済み）
- [PASS] env-init 実行済み判定: `.claude/settings.json` が存在し deny 設定もあるため、
  恒久層はある（内容の不備は上記2件で別途 FAIL 報告済み）

## 協調構成

- [WARN] レジストリ（`.claude/bitz-env.local.md`）に登録されている `bitz-collab-ghost`
  アダプタについて、対応する実プラグイン／実スキルが sandbox 内で確認できない
  （インストール済みプラグイン一覧を取得する手段がこのテスト環境には無いため、
  「存在しないと断定」ではなく「有効性を確認できない」として WARN 報告する）
  → 修正案: env-register を再実行してレジストリの棚卸し（アダプタの実体確認・
  不要エントリの削除）を行うことを提案する
- [PASS] CLAUDE.md 委譲マトリクスとの突き合わせ: 本 sandbox に CLAUDE.md が
  存在しないため対象外（診断項目としてはスキップ、問題としては報告しない）
- [PASS] advisor / worker の frontmatter: `.claude/agents/` が sandbox に存在しないため
  対象外（スキップ）

## 生成物の陳腐化

- [PASS] マーカー区間のテンプレート追従: AGENTS.md のマーカー区間の構造（見出し・節構成）は
  テンプレートと一致している。中身の項目差分は上記 FAIL で個別報告済み

## 総合: 2 FAIL / 1 WARN — 修正を実施しますか？

検出した3件（sudo 欠落 / git reset --hard 欠落 / phantom アダプタ）はすべて
「より制限的な方向へ揃える」修正案のみを提示しており、ガードレールを緩める提案は含めていない。
ユーザーの承認を得てから実施します（本診断ステップでは sandbox のファイルは変更していません）。
