---
implements: FLW-FR-013, FLW-NFR-011, FLW-NFR-012
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/schemas/, plugins/bitz-flow/skills/flow-core/references/operation-catalog.md, plugins/bitz-flow/skills/flow-core/references/output-contract.md, plugins/bitz-flow/skills/flow-core/references/recovery-matrix.md
status: pending
---

### M1公開契約の凍結（enum namespace・intent record・evidence ledger entry・recovery matrix）

- **作業内容**: 実装より先に M1 の公開契約を固定する。FLW-DSN-015 を正として次を定義する。

  - **5つの enum namespace を別 field として分離**する（同名語の混同を避けるため）:
    `write_state`（planned / guarded / pending-intent / mutating / reconciling / done / partial /
    stale / quarantined）、`result_code`（DONE / PARTIAL / INDETERMINATE / STALE / BLOCKED /
    INVALID_INPUT / UNSUPPORTED）、`intent_record_state`（PENDING / RECONCILING / PARTIAL / STALE /
    QUARANTINED / RELEASED）、`gate_status`（PASS / FAIL / BLOCKED）、
    `attempt_status`（STARTED / PASS / FAIL / ABORTED / UNKNOWN）。
  - **guard identity の閉集合**（index / local-ref / remote-tracking-ref / fetch-head / remote-ref）と
    その正規化規則。raw path を key にしない。index は worktree ID を付加した stable file identity、
    remote は canonical host + provider repository ID + ref name のみから導出し local identity を混ぜない。
    symlink・相対 path・case 差・別 worktree・remote alias を正規化し、一意化不能なら write は `BLOCKED`。
  - **intent record v1 schema**: `schema_version` / `operation_id` / `repo_identity` / `targets[]` /
    `fencing_tokens{}` / `snapshot_digest` / `expected_effect_digest` / `intent_record_state` /
    `created_at` / `owner_process` / `receipt_digest` / `previous_record_digest`。
    上書き禁止・同一 operation ID の hash-chain 追記であることを schema 注記に明示する。
    `repo_identity` は local common-dir identity と remote repository identity を監査用に併記する。
  - **evidence ledger entry schema**: `ledger_schema` / `attempt_id` / `epoch_id` /
    `evaluation_objective_id`(immutable) / `leader_epoch` / `fencing_token` / `platform` / `operation` /
    `compatibility_key` / `lease_id` / `eligibility_rule_id` / `positive_control_ids[]` / `oracle_digest` /
    `retryable_failure_codes[]` / `retry_slot_nonce` / `attempt_status` / `issued_at` / `completed_at` /
    `expires_at` / `evidence_id` / `previous_entry_digest`。
    `compatibility_key` の閉集合（scoring rule / runner / adapter / oracle / fixture / prompt / skill /
    result・event schema / 推移的依存 / model identity・date / CLI version / host event-contract version /
    trial 割付）を定義し、`evidence_id` と分離することを明記する。
  - **recovery matrix** を `references/recovery-matrix.md` に表として起こす。行は FLW-DSN-015 の
    (operation, phase, code) → recovery class（retry-read / reconcile-only / replan-human / human-stop）
    → 許可 next_actions → 禁止 の全行。未登録 tuple・未知 field・code と cause の矛盾は `human-stop` へ
    fail-closed とし、到達不能 tuple（単一 ref CAS の原子性により `commit` の `PARTIAL` は到達不能で
    receipt 欠落は `INDETERMINATE` 等）は暗黙 default に頼らず到達不能と明示する。
  - `references/operation-catalog.md` に M1 operation（残る Git read、`git.fetch` / `stage` / `commit` /
    `sync` / `publish-branch` / `delete-remote-branch`、doctor v2）の共通 contract 11 field を
    **契約としてだけ**記入し、`class` / `approval` / `retry` / `recovery` を確定する。
  - `references/output-contract.md` に write 用の追加 field（`write_state` / `stage` / `approval_*` /
    `operation_id` / `idempotency_id`）の compact 表示規約と、M1 で新たに到達する終了コード
    （4 APPROVAL_REQUIRED / 7 PARTIAL / 9 INDETERMINATE）の写像を追記する。
- **完了条件**: 追加した schema がすべて JSON として妥当で、`references/` の記述と schema が同じ
  field 集合・同じ enum 値を指すこと。recovery matrix の各行が (operation, phase, code) で一意であり、
  未登録 tuple の既定が `human-stop` であると明記されていること。
  `python3 <リポジトリ>/scripts/release_check.py` と canonical spec inspect が PASS すること。
- **備考**: 本タスクは契約固定フェーズであり実装コードを含まない。**公開 operation を増やさない**
  （dispatcher の handler 表は変更せず、write 系引数は引き続き副作用なしで `UNSUPPORTED` を返す）。
  既存 M0 schema の key 集合は加算のみとし、意味変更は schema major を上げる。
  Operation Contract の形式は FLW-CON-002 に従うが、同要件は M0 で verified 済みであり
  ライフサイクルに `verified → implementing` の戻り経路が無いため `implements` には宣言しない。
  write operation の実装で同要件の適用範囲が read から write へ広がる扱いは、M1-3 の分解時に
  spec-issue として起票し人間裁定を仰ぐ。
