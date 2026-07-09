# CLAUDE.md

共通ルール（役割・構成・ガードレール・規約・手順）はすべて @AGENTS.md を正とする。

## Claude Code 固有

- スキル開発の全工程は `skill-pipeline` スキルが統括する
  （creator → validator → tester → evaluator →不合格なら optimizer で反復→ packager。
  配置後は instrumenter / observer / improver の自己改善ループ）
- version bump は `/bump <plugin名> [major|minor|patch]`、
  プラグイン追加は `/add-plugin <plugin名>` を使う（`.claude/commands/` のリポジトリ専用コマンド）
- 危険操作の機械的ブロックは `.claude/settings.json` の permissions で強制している
  （AGENTS.md のガードレール節と対応。緩めるときは両方を見直す）
