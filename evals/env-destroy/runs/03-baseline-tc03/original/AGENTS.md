# AGENTS.md — サンプルプロジェクト規約

これはユーザー独自の記述です。プロジェクト固有のコーディング規約や
禁止事項がここに書かれています。

## ガードレール

- `rm -rf` は使わない
- `main` への直接コミット禁止
- 破壊的操作は事前にユーザー確認を取る

<!-- bitz-env:begin -->
## bitz-env による自動生成セクション（編集禁止）

このセクションは env-init が自動生成しました。
- サブエージェント advisor / worker の役割説明
- 防御的協調プロトコルの説明
- 生成物一覧へのリンク
<!-- bitz-env:end -->

## デプロイ手順（ユーザー独自記述）

1. `npm run build`
2. `npm run deploy:staging`
3. レビュー後 `npm run deploy:prod`
