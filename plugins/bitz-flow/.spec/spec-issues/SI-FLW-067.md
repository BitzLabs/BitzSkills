---
id: SI-FLW-067
raised_by: FLW-REV-018（DIN-203 / RSK-404 / RSK-205 / RSK-208 / RSK-306 / DIN-207 / DIN-304 / OPS-202 / RVC-302 / RVC-305）
target: worktree.audit の ground truth 検証・外部起因 ORPHAN の被覆・分類の導出・result schema
proposed_change_type: modify
status: accepted
---
- **目的**: M2 出口条件6「operation 外の変更を audit が検出し quarantine へ接続する」が
  **未達である**という判定（5観点中4観点）を解消する。`FLW-REV-017` は同条件を
  「検出は成立、接続語彙が未整備」と読み `SI-FLW-066` で語彙を接続したが、
  **独立レビューは検出そのものが成立していないと判定した**。

- **発見した事実**（すべて独立レビュアの実測）:
  1. **ground truth が無検証**（`DIN-203` critical / `RSK-404`）—
     receipt chain の `record_digest` を誰も検証しない。**手書き receipt 1件を置くだけで
     外部 worktree を `managed` に洗浄でき**、逆に receipt 1件の欠落で正規の worktree が
     誤って quarantine される。audit の判定根拠そのものが偽装可能である。
  2. **外部起因 `ORPHAN` の2形のうち1形しか見ない**（`RSK-205` / `OPS-202`）—
     `audit_external_binding_change` は `cli.py` から呼ばれず、**managed worktree の
     ディレクトリを外部削除しても audit は `OK` を返す**。さらに receipt へ
     `expected_head` を載せながら audit が比較しないため、
     **managed worktree 内の無許可コミット（2026-08-15 事故の実体）を検出しない**。
  3. **`INDETERMINATE` の分離に穴**（`RSK-208` / `DIN-207`）—
     `receipts` が通常ファイルに置換された場合と `chmod 000` の場合はどちらも
     `is_dir()` が False を返して「receipt が1件も無い」枝へ落ち、
     **全 worktree が外部起因に見える**。ファイル欠落・自 operation の中断も同様に誤分類する。
     `FLW-DSN-016` §7 が名指しで禁じた「分類の推測」に当たる。
  4. **`release_class` が定数**（`RSK-306` / `DIN-304` / `RVC-302`）—
     `classify_quarantine` へ渡す `QuarantineEvidence` は全フィールドが固定リテラルで、
     §6 の4区分のうち `worktree-unresolved` 以外は公開経路から生成され得ない。
     分類は計算ではなく表示である。
  5. **新設語彙が result schema の閉集合外**（`RVC-305` / `DIN-304`）—
     `worktree_state: "ORPHAN"` / `quarantine` / `recovery_class` は schema に定義が無く、
     **出口条件4（enum 三者照合）を新たに崩している**。

- **提案する修正**:
  - receipt chain の `record_digest` を読み出し時に検証し、chain 不整合は
    `INDETERMINATE`（`human-stop`）とする。欠落と改竄を区別する
  - `audit_external_binding_change` を公開 audit から呼び、
    directory 消失・registry 改変・`expected_head` 乖離を検出対象に加える
  - `managed_worktrees_status` の照合不能条件を store 単位（`is_dir()` False・
    permission・欠落）まで広げる
  - `QuarantineEvidence` を receipt chain の実状態から構成し、4区分が実際に分岐するようにする
  - `worktree_state` / `quarantine` / `recovery_class` を result schema の閉集合へ登録し、
    enum 三者照合の対象に入れる

- **対象ファイル**: `plugins/bitz-flow/skills/flow-core/scripts/flowlib/` の
  `cli.py` / `result.py` / `worktree_runtime.py` / `worktree_capability.py` / `worktree_cleanup.py`、
  `tests/test_flow_m2_runtime.py`、`.spec/design/FLW-DSN-016.md`、
  `plugins/bitz-flow/skills/flow-core/references/operation-catalog.md`

- **確認観点**: 偽装 receipt・欠落 receipt・外部削除・無許可コミット・store 破損の
  各条件に**陽性対照と陰性対照**を置くこと。4区分がすべて公開経路から生成され得ること。

- **影響推定・ロールバック**: 出荷面は M0 read-only のままであり利用者影響は無い。
  worktree 系は `UNSUPPORTED` を継続する。

- **依存**: 出口条件6と条件4の判定に直結する。Completion Gate の前提。
