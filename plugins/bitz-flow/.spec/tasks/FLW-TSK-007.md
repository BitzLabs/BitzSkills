---
implements: FLW-FR-003, FLW-NFR-002
depends_on: [FLW-TSK-005]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/result.py
status: done
---

### M0 result object と compact renderer の実装

- **作業内容**: FLW-TSK-005 が凍結した契約に従い `flowlib/result.py` を実装する。
  result object の生成、`result_digest` の算出（自身を除く result を UTF-8・key 辞書順・
  余分な空白なし・schema が許可した整数表現へ正規化した byte 列の SHA-256）、
  snapshot fingerprint の算出（FLW-DSN-005 の canonical bytes から計算し、
  呼出時の `--snapshot` と不一致なら `STALE`）、truncation と cursor
  （`shown` / `total` / snapshot 拘束 cursor と絞込み next action）を持たせる。
  compact renderer は固定 token・固定 field 順・1項目1行を守り、0件 field と null を省略する。
  blocking / error 項目を最優先し、次に変更対象、通常項目の順で描画する。
  上限超過時は `TRUNCATED shown=<n> total=<m> cursor=<snapshot-bound>` と絞込み action を必ず返す。
  JSON renderer は operation 別 JSON Schema を満たす result object をそのまま出力する。
  renderer は raw output へアクセスしない（依存方向は renderer ← result object）。
  path は repo 相対表示を既定とし、repo 外 target だけ canonical absolute path を返す。
  `summary` は事実だけを述べ、推奨判断は `next_actions` へ分離する。
- **完了条件**: 同じ result から compact と JSON が同じ判定（`code` / `exit_code` / `ok`）を返すこと。
  raw command・stdout・stderr・environment・credential が出力経路に存在しないこと。
  digest が同一 result に対して決定論的であること。
- **備考**: byte 削減の目標値（status で median 70%以上、diff-summary で 80%以上）は
  FLW-TSK-011 の fixture と FLW-TSK-012 の実測で判定する。本タスクでは renderer が
  情報を落とさずに短くする構造（固定 token・省略規則・truncation の可視化）までを担う。
