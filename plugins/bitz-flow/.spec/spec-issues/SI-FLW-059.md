---
id: SI-FLW-059
raised_by: FLW-REV-016 M2 Exit再レビュー
target: 公開dispatcherのworktree write網羅とauditの契約層接続
proposed_change_type: modify
status: open
---

- **目的**: `FLW-REV-015:GP-001` の原文が求める「**全** worktree write を公開 dispatcher から
  起動して確認する」を満たし、M2 出口条件の「operation 外変更の audit 検出・quarantine 接続」を
  公開経路で成立させる。

- **発見した事実**（`FLW-REV-016:SYN-006` / `SYN-011` / `SYN-016`）:
  - `tests/test_flow_m2_runtime.py` の8件のうち7件は `worktree_runtime` を直呼びし、
    dispatcher を通るのは `create --plan`（read-only）1件だけである。
    resume / finish / discard / audit と全 fault 経路は公開入口を通らない。
  - `_op_worktree` の audit 分岐は private `_git` を直呼びする
    `git worktree list --porcelain` の薄いラッパで、失敗が result にならず traceback になる。
    `--limit` / `--timeout` も無視される。外部変更検出から quarantine までが未接続である。
  - 公開 operation 集合が `PUBLISHED_OPERATIONS` と `_HANDLERS` に二重定義され、
    機械検査は後者だけを見るため前者は死んだ宣言になっている。公開 CLI の `--help` は
    「M0: read-only の3 operation」、`--apply` / `--confirm` / `--approval-ref` は
    「（M1 以降）」のままで、destructive write を公開した事実と逆を述べる。

- **提案する修正**:
  1. 4つの write operation と主要 fault 経路を `cli.main` 経由の E2E で再構成する。
  2. `worktree.audit` を契約層（result / エラー分類 / `--limit` / `--timeout`）へ載せ、
     外部変更検出から quarantine までを公開経路で接続する。
  3. 公開集合を SSOT 化して機械検査を一本化し、`--help` 文言を実態へ揃える。

- **対象ファイル**: `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`、
  `tests/test_flow_m2_runtime.py`、`tests/test_flow_contract.py`、
  `plugins/bitz-flow/skills/flow-core/references/operation-catalog.md`

- **確認観点**:
  - 全 write operation が公開入口経由で実 Git 副作用を起こし、capability 検証が
    各副作用直前に走ること。
  - operation 外の worktree 変更を audit が検出し、quarantine へ接続されること。
  - `--help` と operation-catalog が公開集合と一致し、機械検査で担保されること。

- **影響推定・ロールバック**: 公開 CLI の契約表示が変わるため、
  `operation-catalog.md` の 11 field 契約（`FLW-REV-016:SYN-020`）と併せて更新する。

- **依存**: `FLW-REV-016:GP-001`。予算は `FLW-REV-016:GP-005` の再裁定に従う。
