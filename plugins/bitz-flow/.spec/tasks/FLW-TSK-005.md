---
implements: FLW-FR-003, FLW-CON-002
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/schemas/, plugins/bitz-flow/skills/flow-core/references/operation-catalog.md, plugins/bitz-flow/skills/flow-core/references/output-contract.md
status: pending
---

### M0 公開結果契約の凍結（result envelope と operation 別 JSON Schema）

- **作業内容**: 実装より先に公開契約を固定する。FLW-DSN-003 の internal result object を
  `schemas/result-v1.schema.json` として起こし、`schema` / `result_digest` / `operation` / `ok` /
  `code` / `exit_code` / `repo` / `snapshot` / `operation_id` / `idempotency_id` / `approval` /
  `summary` / `data` / `audit` / `invocation` / `warnings` / `truncated` / `next_actions` を
  必須・型・enum つきで定義する。`data` は FLW-DSN-012 の共通 data 契約
  （`target` / `preconditions` / `effects` / `postconditions` / `concurrency_key` / `evidence` /
  `completed_steps` / `remaining_steps` / `cause` / `items` / `page`）を持ち、未知 field を許容するが
  既存 field の意味を変えない。
  `schemas/operations/` に M0 の3 operation（`repo.inspect` / `git.status` / `git.diff-summary`）の
  data schema を作る。FLW-DSN-005 の Read operations 表を出力 field の正とする。
  `references/operation-catalog.md` には FLW-DSN-012 の共通 contract 11 field を M0 の3 operation
  について記入する（`class: read` / `approval: none` / `retry: safe` / `recovery` 空）。
  `references/output-contract.md` に compact renderer の固定 token・固定順序・1項目1行・
  0件 field と null の省略・`TRUNCATED shown=/total=/cursor=` 書式・終了コード表
  （0 OK / 2 INVALID_INPUT / 3 BLOCKED / 4 APPROVAL_REQUIRED / 5 UNAVAILABLE / 6 STALE /
  7 PARTIAL / 8 UNSUPPORTED / 9 INDETERMINATE）と `data.cause` の許可語彙を定義する。
  `result_digest` の正規化規則（自身を除く result を UTF-8・key 辞書順・余分な空白なしへ
  正規化した byte 列の SHA-256）を明記する。
- **完了条件**: 3 operation の schema が JSON として妥当で、`references/` の記述と schema が
  同じ field 集合を指すこと。M1 以降の operation を先取りして定義しないこと。
  `python3 scripts/release_check.py` と canonical spec inspect が PASS すること。
- **備考**: 本タスクは実装コードを含まない（契約固定フェーズ）。key 集合は加算のみで、
  意味変更は schema major を上げる規則を schema 内へ注記する。
