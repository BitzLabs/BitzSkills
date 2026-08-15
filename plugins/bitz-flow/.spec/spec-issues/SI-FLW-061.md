---
id: SI-FLW-061
raised_by: investigation-2026-08-15-capability-reduction.md（選択肢B）
target: 承認capabilityの条件付き縮退（B2）とtrusted key registry境界の是正
proposed_change_type: modify
status: accepted
---

- **目的**: 承認の既定を `--confirm <operation_id>` ＋ 単回 nonce ＋ `expires_at` とし、
  署名検査を **trusted key registry が存在する配備でのみ**有効化する。
  鍵隔離を署名モードの前提条件として明文化し、どちらのモードで判定したかを result へ出す。
  あわせて `apply()` が自ら registry を読むよう是正する。

- **由来**: 2026-08-15 の裁定（B2 採用）。
  `.spec/reports/decision-2026-08-15-capability-b2.md`、
  材料は `.spec/reports/investigation-2026-08-15-capability-reduction.md`。

- **発見した事実**:
  - **署名は M1 からの流用**である。`FLW-DSN-016` §4 は「M1 の capability envelope を
    そのまま再利用」「新規機構ではない」と明記する。M1 の原型（`FLW-DSN-015` L248-254）は
    quarantine 解除の文脈で署名対象に `reviewer` を持ち、registry は repository owner が
    管理していた。M2 への移植で `reviewer` が落ち、承認者 ≠ executor の前提が失われた。
  - **`operation_id` が承認 scope 全体を既に束縛している**。
    `worktree_runtime.plan()` は `WorktreeApprovalContext` 全体を含む facts の digest を
    `operation_id` とし、apply は `--confirm` との一致に加えて**各副作用の直前に plan を
    再導出**して同一性を再検査する（`worktree_runtime.py:306` / `:336-340`）。
    capability の scope 検査・freshness 検査は同じ束縛の二重持ちである。
  - capability が固有に足しているのは `expires_at`（`RuntimePlan` に有効期限 field が無い）と
    nonce 単回性の2つだけで、どちらも暗号を必要としない。
  - `worktree_runtime.apply()` は `public_keys` を呼び出し側から受け取り、registry を自ら
    読まない（`FLW-REV-016:RSK-204`）。公開経路は `cli.py:405` が
    `load_trusted_keys()` を呼んで強制しているが、多層防御としては弱い。

- **提案する修正**:
  1. 署名検査（`algorithm` / `key_id` / signature）を条件付きにする。
     trusted key registry が存在しない配備では要求しない。
  2. 既定モードの承認入力を `--confirm <operation_id>` ＋ `--nonce` ＋ `expires_at` とする。
     `--capability-file` は署名モードでのみ必須とする。
  3. 承認モードを result へ明示する（候補: `data.approval_mode` =
     `"plan-digest"` / `"signed-capability"`）。schema 追加の要否を含めて決める。
  4. `apply()` が自ら `load_trusted_keys(common_dir)` を呼ぶ。`public_keys` 引数は削除するか、
     テスト専用の注入口として明示的に分離する。
  5. `FLW-DSN-016` §4 を B2 の規範へ改訂し、署名モードの前提条件（鍵隔離）を明記する。

- **対象ファイル**: `plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py`、
  `.../worktree_runtime.py`、`.../cli.py`、
  `plugins/bitz-flow/skills/flow-core/references/operation-catalog.md`、
  `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`、
  `tests/test_flow_m2_capability.py`、`tests/test_flow_m2_runtime.py`

- **確認観点**:
  - registry 不在の配備で、署名なしの承認が成立し、かつ `--confirm` 不一致・nonce 再利用・
    期限切れ・承認後の状態変化がいずれも停止すること。
  - registry 存在の配備で、従来どおり署名検査が有効になること。
  - `apply()` を library 直呼びしても registry 境界が効くこと（テストの注入口を分離しても、
    既定経路では registry から読むこと）。
  - 承認モードが result から判別でき、モードの取り違えが検出できること。
  - `M2-FLT-010`〜`015`（署名系 fault）が新しい2モードのどちらに属するか整理されていること。

- **影響推定・ロールバック**: worktree operation は 2026-08-15 の裁定で未公開
  （`UNSUPPORTED`）であるため、利用者影響は現時点で無い。
  署名モードを残すため、隔離配備へ進む道は閉じない。

- **依存**: `SI-FLW-057`（同じ `apply()` の例外分類を触る）。着手順の調整が要る。
  予算は後続の予算裁定に従う。
