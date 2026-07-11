# run 03 — TC-03（スキル名の衝突解決）

- ケースID: TC-03
- モード: ベースライン（env-register SKILL.md 未読）
- 実行日時: 2026-07-11

## 手順の記録

1. 入力プロンプト「second-adapter も登録して」を受領。
2. `.claude/bitz-env.local.md` を確認。既に `first-adapter`（priority: 1, routes.delegate: ex-delegate）
   が登録済みだった。
3. `plugins/second-adapter/plugin.json` の `metadata.collab.skills.delegate` も `ex-delegate` を
   宣言しており、実スキル名が既登録アダプタと重複していることに気づかなかった
   （文字列比較による衝突検知の手順を持たない）。
4. `second-adapter` セクションをそのまま追記した。priority も既登録と同じ 1 を設定した。
5. 衝突についてユーザーへ報告していない。名前空間化（アダプタ名プレフィックス付与）も行っていない。

## 成果物一覧

- `sandbox/.claude/bitz-env.local.md`（second-adapter セクションを追記。ただし routes.delegate が
  first-adapter と同じ `ex-delegate` のまま重複登録されている）

## 備考（アサーション事前チェック）

- 衝突報告: していない
- 名前空間化して登録: していない（`ex-delegate` のまま重複）
- priority で優先順を明示・既登録の priority 不変: 既登録 first-adapter の priority: 1 は変更していないが
  （不変という点のみ結果的に満たす）、衝突自体を検知していないため優先順の明示的な使い分けはできていない
