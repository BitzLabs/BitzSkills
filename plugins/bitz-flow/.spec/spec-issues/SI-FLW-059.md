---
id: SI-FLW-059
raised_by: FLW-REV-016 M2 Exit再レビュー
target: 公開dispatcherのworktree write網羅とauditの契約層接続
proposed_change_type: modify
status: accepted
---

- **目的**: `FLW-REV-016:GP-001`（新 scope）が求める「M2 scope の worktree write を
  公開 dispatcher から起動して確認する」を満たし、M2 出口条件の
  「operation 外変更の audit 検出・quarantine 接続」を公開経路で成立させる。

- **scope**（2026-08-15 の裁定。`.spec/reports/decision-2026-08-15-si-flw-057-059.md`）:
  対象は `FLW-REV-016:SYN-006` と `SYN-011` の2件。
  **`SYN-016`（公開集合の二重定義・`--help` 文言）は PR #275 で解消済みのため除外**した。
  また同日の scope 縮小により、対象 write は **`create` / `resume`** である
  （`finish` / `discard` は M3 へ移送）。

- **発見した事実**:
  - `tests/test_flow_m2_runtime.py` の8件のうち7件は `worktree_runtime` を直呼びし、
    dispatcher を通るのは `create --plan`（read-only）1件だけだった。
    fault 経路はすべて公開入口を通らない（`FLW-REV-016:SYN-006`）。
    なお 2026-08-15 の出荷面限定により、現在 dispatcher 経由の worktree は
    `UNSUPPORTED` である。本 issue の E2E は**公開を戻す時点で**成立させる。
  - `_op_worktree` の audit 分岐は private `_git` を直呼びする
    `git worktree list --porcelain` の薄いラッパで、失敗が result にならず traceback になる。
    `--limit` / `--timeout` も無視される。外部変更検出から quarantine までが
    未接続である（`FLW-REV-016:SYN-011`）。

- **提案する修正**:
  1. `create` / `resume` と主要 fault 経路を `cli.main` 経由の E2E で再構成する。
     公開を戻すタイミングは M2 出口条件の充足時とする。
  2. `worktree.audit` を契約層（result / エラー分類 / `--limit` / `--timeout`）へ載せ、
     外部変更検出から quarantine までを公開経路で接続する。

- **対象ファイル**: `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`、
  `tests/test_flow_m2_runtime.py`、`tests/test_flow_contract.py`、
  `plugins/bitz-flow/skills/flow-core/references/operation-catalog.md`

- **確認観点**:
  - `create` / `resume` が公開入口経由で実 Git 副作用を起こし、capability 検証が
    各副作用直前に走ること。
  - operation 外の worktree 変更を audit が検出し、quarantine へ接続されること。
  - 公開を戻すとき、`cli.py` の import 時整合検査（`PUBLISHED_OPERATIONS` ⇔ `_HANDLERS`）が
    同じ変更セットで通ること。

- **影響推定・ロールバック**: 公開 CLI の契約表示が変わるため、
  `operation-catalog.md` の 11 field 契約（`FLW-REV-016:SYN-020`）と併せて更新する。

- **依存**: `FLW-REV-016:GP-001`。予算は後続の予算裁定に従う。
