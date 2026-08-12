---
id: SI-FLW-050
raised_by: FLW-REV-013（独立5観点レビュー・FAIL 2.31）
target: FLW-DSN-016・FLW-DSN-012
proposed_change_type: modify
status: accepted
---
- **目的**: **`worktree_state` が互いに排他でない3つの軸を単一 enum へ潰している**状態を
  解消する。この曖昧さは finish の許可判定に直結し、**未コミット作業の喪失可否を決める**。

- **確認済みの欠陥**（`FLW-REV-013:SYN-004` / `SYN-030` / `SYN-032`。
  2026-08-13 に値集合を機械確認）:

  `FLW-DSN-016.md:92` の定義:

  ```
  worktree_state = ABSENT, ACTIVE_CLEAN, ACTIVE_DIRTY, PR_OPEN, MERGED_EXACT,
                   REMOTE_ADVANCED, WORKTREE_MISMATCH, ORPHAN, FAILED_RETAINED
  ```

  この9値には**直交する3軸が兄弟として並んでいる**:

  | 軸 | 値 |
  |---|---|
  | 作業ツリーの状態 | `ACTIVE_CLEAN` / `ACTIVE_DIRTY` |
  | PR の状態 | `PR_OPEN` |
  | merge の状態 | `MERGED_EXACT` / `REMOTE_ADVANCED` |

  これらは同時に成立する。「未コミット変更があり、PR が open で、tip が merge 済み」は
  実運用で普通に起こるが、単一 enum は1値しか取れない。**同時成立時の優先順位規定が
  本書に存在しない**ため、判定が非決定になる。

  `FLW-DSN-012` は「危険側へ倒す」という原則を持つが、その適用には**全順序**が必要で、
  9値の全順序は定義されていない。

- **なぜ重大か**: **`MERGED_EXACT` は `finish` の許可前提**である。
  `dirty × MERGED_EXACT` の解決が `MERGED_EXACT` に倒れると、finish が
  **未コミット作業ごと worktree を削除**する。`FLW-DSN-016` §5 は未コミット作業を
  「復元できない」と認識しているにもかかわらず、この経路に防御が無い。

  さらに §9 の fixture で dirty を扱うのは **`M2-FLT-031`（discard 用）の1件のみ**で、
  **finish 側の dirty fixture が存在しない**。テストでも検出されない。

- **併発する欠陥**:

  1. **判定述語（決定表）が本書に無い**（`SYN-030`）。三者照合（設計 ⊆ schema ⊆ 実装）は
     **値集合しか見ない**ため、「値は一致するが意味が乖離する」経路が塞がっていない
  2. **`work_unit_state` は12値の列挙のみで遷移関係が無く**、`worktree_state` の9値のうち
     3値は `FLW-DSN-012` の写像表から**到達できない**（`SYN-032`）

- **提案する修正**（**選択肢を提示し、裁定を求める**）:

  | 案 | 内容 | 評価 |
  |---|---|---|
  | **案A** | **直交軸へ分離する**。`worktree_worktree_state`（CLEAN / DIRTY / ABSENT / MISMATCH）、`worktree_branch_state`（ACTIVE / MERGED_EXACT / REMOTE_ADVANCED / ORPHAN）、`worktree_pr_state`（NONE / OPEN / MERGED）の3 enum とし、operation の許可条件を**軸の組合せ**で書く | **推奨。** 同時成立が表現でき、finish の許可条件を「branch が MERGED_EXACT **かつ** worktree が CLEAN」と明示できる。曖昧さが構造的に消える |
  | 案B | 単一 enum を維持し、**9値の全順序を定義**する（危険側優先） | 変更は局所的だが、軸が増えるたびに値が組合せ爆発する。`PR_OPEN` と `ACTIVE_DIRTY` のどちらが危険かという本質的に無意味な比較を強いられる |
  | 案C | 単一 enum を維持し、同時成立しうる組合せを**複合値として列挙**する | 案B の欠点に加え値数が増える。非推奨 |

  **推奨は案A。** ただし `worktree_state` は M2 で新設する enum であり
  **M0 / M1 で凍結済みの namespace ではない**ため、分離の破壊的影響は M2 内に閉じる
  （`branch_audit_state` は既に別 enum として分離されており、案A はその方針の一貫適用でもある）。

  裁定後、次を併せて確定する:

  - **判定述語（決定表）を設計に明記**し、三者照合の対象へ含めるか
    （現在は値集合のみが照合対象）
  - `work_unit_state` の**遷移関係**の定義と、到達不能値3件の解消
  - **finish 側の dirty fixture の追加**（現在 discard 用1件のみ）

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`（§2 enum・§8 recovery matrix・§9 fixture catalog）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-012.md`（状態写像表）

- **確認観点**:
  - 同時成立しうる状態が**表現できる**こと（dirty かつ merged が同時に立つ）
  - `finish` の許可条件が**曖昧さなく**書けること
  - 全 enum 値が写像表から**到達可能**であること
  - 未コミット作業がある worktree に対する finish が fixture で**検証されている**こと

- **影響推定・ロールバック**: M2-3（create / resume / audit）と M2-5（finish / discard）の
  設計に波及する。`FLW-DSN-012` の写像表と `FLW-DSN-006` の分類表も追随が必要。
  M0 / M1 の凍結 enum には触れない。未実装のため文書改訂のみで戻せる。

- **依存**: `SI-FLW-047`（区分の軸を証跡へ移す場合、状態の表現と整合させる必要がある）。
  `SI-FLW-052`（判定述語を三者照合の対象へ含めるかは検証の設計と一体）。
