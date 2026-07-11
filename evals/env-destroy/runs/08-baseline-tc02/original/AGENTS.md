# AGENTS.md — サンプルプロジェクト共通ルール

このファイルが全エージェント共通ルールの正。

このプロジェクトでは決済 API を扱うため、通貨計算は必ず Decimal 型を使うこと。
浮動小数点での金額計算は禁止する（ユーザー独自の記述）。

<!-- bitz-env:begin -->
## ガードレール（bitz-env 生成）

### 禁止（実行しない）

- `rm -rf` / `git push --force` / `git reset --hard` / `git clean -f` / `sudo`
- デフォルトブランチへの直接コミット（変更時は必ずブランチを切る）
- 認証情報・トークン類（`~/.claude/.credentials.json`・`.env` 等）の読み取り・出力

### 事前確認が必要（ユーザーの明示承認なしに実行しない）

- リポジトリ外への書き込み・上書き・削除
- `git push`（外部公開）

### 検証義務

- 委譲先・相談先の「成功しました」という自己申告を信用せず、
  テスト・機械チェックを自分で再実行して確認する

> 対応する機械強制: `.claude/settings.json` の permissions と bitz-env 同梱フック。
> ルールを緩めるときは本節と permissions の両方を見直す（同期チェックは env-doctor）
<!-- bitz-env:end -->

## コミット・PR 規約

- コミットタイトルは Conventional Commits に従う — `<type>(<scope>): <説明>`
- 1 PR = 1 関心事（`git revert` で丸ごと戻せる粒度を保つ）

## デプロイ手順（ユーザー独自記述）

1. `npm run build`
2. `npm run deploy:staging`
3. レビュー後 `npm run deploy:prod`
