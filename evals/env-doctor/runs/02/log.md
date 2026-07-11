# run 02 — TC-01 / スキルあり

- **ケースID**: TC-01
- **モード**: スキルあり（env-doctor SKILL.md + env-init/references/permissions.md を読んだ上で忠実に実行）
- **実行日時**: 2026-07-11
- **入力プロンプト**: 「環境を診断して」
- **sandbox**: `evals/env-doctor/runs/02/sandbox/`（run01と同一のズレ(1)(2)(3)を注入）

## 手順の記録

1. `plugins/bitz-env/skills/env-doctor/SKILL.md` と
   `plugins/bitz-env/skills/env-init/references/permissions.md` を読み、
   診断項目（ガードレール3層突き合わせ／協調構成突き合わせ／生成物の陳腐化）と
   出力フォーマット（PASS/WARN/FAIL チェックリスト）を把握
2. sandbox の `.claude/settings.json` の deny 配列を permissions.md の最小集合と突き合わせ
   → `Bash(git reset --hard:*)` の欠落を検出（ズレ(2)）
3. sandbox の AGENTS.md マーカー区間の禁止リストを、env-init テンプレート原本
   （`AGENTS-template.md` の禁止リスト、および settings.json の deny）と突き合わせ
   → `sudo` の記載欠落を検出（ズレ(1)）
4. sandbox の `.claude/bitz-env.local.md` のアダプタエントリ（bitz-collab-ghost）について、
   実体（インストール済みプラグイン）との突き合わせを試みたが、このテスト環境では
   インストール済みプラグイン一覧を取得する手段が無いため「確認不能」として WARN 報告
   （ズレ(3)を検出。ただし FAIL ではなく WARN 扱いとした点は判定の余地あり、備考に記載）
5. 「してはいけないこと」節に従い、修正の実施はせず診断結果と修正案の提示のみに留めた
6. 診断結果を `runs/02/diagnosis.md` に保存

## 成果物一覧

- `runs/02/diagnosis.md`（PASS/WARN/FAIL チェックリスト形式の診断結果）
- `runs/02/log.md`（本ファイル）

## 備考

- ズレ(1)(2)(3) すべてを検出できた（ベースライン run01 は(2)のみを弱く言及、(1)(3)は未検出）
- 修正案はすべて「より制限的な方向へ揃える」方向のみで、緩和方向の提案は無い
- sandbox のファイルは診断中に一切変更していない
