---
id: SI-FLW-064
raised_by: FLW-REV-017 data-integrity（DIN-202）
target: receipt payload の変更対象記録と worktree.audit の外部変更検出
proposed_change_type: modify
status: accepted
---

- **目的**: M2 出口条件「operation 外変更の audit 検出・quarantine 接続」を成立させる。

- **裁定**: 2026-08-16 の第2次予算裁定が本項目を順序3として列挙しているため、
  その実行単位として accepted で起票する
  （`.spec/reports/decision-2026-08-16-m2-remediation-budget-2.md`）。

- **発見した事実**:
  - receipt payload は `operation_id` / `state` / `completed_steps` だけで、
    **変更対象を一切指していなかった**（`FLW-REV-017:DIN-202`。前回 `SYN-013` として P2 だったが
    出口条件を塞いでいることが判明し critical へ格上げされた）。
  - このため `SI-FLW-059` の実装時に audit の外部変更検出が成立せず、
    「不可」を宣言する形で出荷せざるを得なかった。git の registry は
    `git worktree add` で必ず登録されるため、registry 照合では bitz-flow が作ったものと
    外部で作られたものを区別できない。

- **実装した修正**:
  1. receipt payload へ `target`（`action` / `path` / `branch` / `worktree_root` /
     `expected_head`）を載せる。事後の監査と復旧に要る最小の観測値に限る。
  2. `managed_worktrees()` を追加し、receipt の DONE 記録から「この operation 群が
     管理している worktree」を導く（`create` / `resume` で加え、`finish` / `discard` で除く）。
  3. `worktree.audit` を receipt 照合へ切り替え、外部変更を検出したら `BLOCKED` にして
     next action で人間の検分を促す（自動修復はしない）。

- **確認観点**:
  - 陽性対照: operation 外で作った worktree を検出し `BLOCKED` になること。
  - 陰性対照: operation が作った worktree を外部変更にしないこと（常に BLOCKED なら
    反証できない検査になる）。
  - receipt が変更対象を持つこと。

- **影響推定・ロールバック**: receipt の payload が増える。既存 receipt には `target` が
  無いため、`managed_worktrees()` は `target` を持たない記録を無視する（過去の receipt を
  「管理外」とは扱わない設計にはしていない点が残課題）。

- **依存**: `SI-FLW-060`（M3 の破壊系 step 語彙）と receipt 形式で重なる。
  本 issue は M2 scope（`create` / `resume` / `audit`）に必要な最小限に絞る。
