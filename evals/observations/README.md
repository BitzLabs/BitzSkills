# observations — スキル実行の観察ログ

`skill-observer` が記録し `skill-improver` が消費する自己改善ループのログ置き場。

- `observations.jsonl` — 1行1観察のJSONL。問題（partial/fail）のみ記録される
- 書式の正典: `plugins/skill-creator/skills/skill-observer/references/observation-schema.md`
- 行の追記は observer、`status` / `resolved_by` の更新は improver のみが行う
