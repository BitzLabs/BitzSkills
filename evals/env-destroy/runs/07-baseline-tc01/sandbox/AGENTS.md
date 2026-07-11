# AGENTS.md — サンプルプロジェクト共通ルール

このファイルが全エージェント共通ルールの正。

このプロジェクトでは決済 API を扱うため、通貨計算は必ず Decimal 型を使うこと。
浮動小数点での金額計算は禁止する（ユーザー独自の記述）。


## コミット・PR 規約

- コミットタイトルは Conventional Commits に従う — `<type>(<scope>): <説明>`
- 1 PR = 1 関心事（`git revert` で丸ごと戻せる粒度を保つ）

## デプロイ手順（ユーザー独自記述）

1. `npm run build`
2. `npm run deploy:staging`
3. レビュー後 `npm run deploy:prod`
