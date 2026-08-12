---
id: FLW-REV-011
title: "M2 設計ギャップ差分レビュー"
status: pending
version: 1.0
updated: 2026-08-12
owner: claude
decision: FAIL
---

# 設計レビュー統合レポート — M2 設計ギャップ（SI-FLW-041 / SI-FLW-042）

- **review_id**: FLW-REV-011
- **対象**: `SI-FLW-041`、`SI-FLW-042`、`decision-2026-08-12-m2-design-gaps.md`、
  `FLW-DSN-015` の変更箇所（guard identity 節・namespace 表節）
- **判定**: **FAIL**
- **集計スコア**: 2.47（PASS ≥ 3.5 / CONDITIONAL_PASS ≥ 2.5）
- **非適用**: data-integrity（今回の差分は永続データ構造を変えない）、
  business（スコープ判断は `decision-2026-08-12-m2-design-gaps.md` で裁定済み）

## 観点別スコア

| 観点 | スコア | 重み（正規化後） | 主要所見 |
|---|---:|---:|---|
| consistency | 2.40 | 0.25 | closed enum が「値の正」と宣言した文書と6欠落・2捏造でずれている |
| operations | 2.50 | 0.33 | guard の解放経路・承認の束縛・凍結対象の一致が未定義 |
| risk | 2.50 | 0.42 | 追加2種が M1 の local target 保証を名前だけ継承し実体を継承していない |

findings: 統合前 34 件 → 重複排除後 21 件（P0: 5 / P1: 11 / P2: 4 / P3: 1）

## 判定の意味

**方向（guard identity を足して3者を守る）は3観点とも正しいと認めている。**
問題は、追加した2種が M1 が local target へ課した保証（CAS 相当・stable identity・
capability 縮退・fault fixture）を**名前だけ継承して実体を継承していない**ことと、
`SI-FLW-039` を防ぐための namespace 改修が**同型の二重定義をもう一段作った**ことにある。

3観点が独立に同じ P0（enum 不一致）へ到達しており、単独観点の見落としではない。

## P0（5系統・重複排除後）

| ID | 内容 | 由来 |
|---|---|---|
| SYN-001 | closed enum が「値の正」と宣言した設計文書と一致しない | RVC-001 / OPS-003 / RSK-010 |
| SYN-002 | 承認と guard key が結合せず TOCTOU が閉じない | OPS-002 / RSK-002 |
| SYN-003 | worktree guard と index guard が互いに素で、削除中の worktree に stage が走る | RSK-001 |
| SYN-004 | path digest key が時間をまたいで別実体を同一視する | RSK-003 |
| SYN-005 | worktree guard の解放経路が未定義で無期限 BLOCKED から復帰できない | OPS-001 |

**SYN-004 は `FLW-REV-008` が捕まえた「commit 誤帰属」の worktree 版**である。
discard の承認待ち中に同じ work-id で worktree が作り直されると、manifest も guard key も
一致するため誰も止めず、新しい実体（未コミットの作業を含む）を削除する。
失うものは remote branch と違って復元できない。

## 実装で確認した事実（レビュー結果の裏取り）

| 指摘 | 確認方法 | 結果 |
|---|---|---|
| RSK-006 | `grep canonical_index_target` | `git_sync.py:234` が literal `"main"` を渡している。canonical 導出関数が無い |
| RSK-005 | 不在 path で `_case_sensitive_filesystem` を実行 | `True`（case-sensitive 扱い）を返す。worktree-dir は create 時に必ず不在 |
| RSK-001 | `guard.py` の key 生成を確認 | index key と worktree key に包含関係の規定が無い |
| SYN-001 | `FLW-DSN-012` の写像表を直接確認 | WorkUnit state は12種。宣言した8種とは6欠落・2捏造 |

## 人間への裁定依頼

### 1. 補強詳細設計を作るかどうか

裁定記録 `decision-2026-08-12-m2-design-gaps.md` は「`FLW-DSN-006` は揃っているので
M1 の `FLW-DSN-015` に相当する補強設計は不要」と判断した。**この判断を見直す必要がある。**

P0 5系統のうち4系統（SYN-002 / 003 / 004 / 005）は、`FLW-DSN-006` にも `FLW-DSN-015` にも
書かれていない**新しい安全機構**を要求している。spec-issue の追記で収まる規模ではない。

### 2. `registered-active` の扱い

`FLW-DSN-006` の create 終端 `registered-active` を `ACTIVE_CLEAN` へ統合するか、
12値目として残すかは設計意図の問題で、文書から一意に決められない（RVC-002 / RSK-010）。

### 3. guard 取得を承認の前へ倒すか

裁定は「guard は承認の後」を選んだが、その選択のコスト（SYN-002 / 004 と承認の使い回し）が
文書に記されていない。前へ倒すと承認待ちの間 guard を保持して他 operation を長時間 BLOCKED
にする副作用がある。少なくとも却下理由の明記が要る（RSK 未解決項目）。

## Gate 前提条件（blocking）

| ID | 条件 |
|---|---|
| GP-001 | `work_unit_state` / `worktree_state` の値を `FLW-DSN-012` / `FLW-DSN-006` と一致させ、三者照合を機械化してから M2 の契約を凍結する |
| GP-002 | repo 外承認を capability 化し、guard key・親 directory identity・非存在証明・期限・単回 nonce を署名対象に含めて apply 直前に再照合する |
| GP-003 | worktree の guard を取る operation は、その worktree に属する index target を同じ acquire に含める包含規約を定める |
| GP-004 | worktree の instance identity（gitdir 内容・HEAD OID・create 時 nonce）を precondition に入れ、apply 直前に CAS 照合する |
| GP-005 | worktree guard の quarantine 解除区分を定義し、正規の解放経路を用意する |

上記が満たされるまで **M2 の契約凍結へ進めない**。
