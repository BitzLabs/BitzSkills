# 裁定記録 — SI-FLW-050（`worktree_state` の直交軸分離）

- **日付**: 2026-08-13
- **裁定者**: hide
- **対象**: `SI-FLW-050`
- **提示方法**: issue の推薦つき選択肢に、実ファイル検証で判明した第4の案を加えて提示し、選択を得た
- **前提**: `FLW-REV-013`（独立5観点レビュー・FAIL 2.31）。
  先行して `SI-FLW-047` / `048`（`decision-2026-08-13-si-flw-047-048.md`）、
  `SI-FLW-049` / `055`（`decision-2026-08-13-si-flw-049-055.md`）を裁定済み
- **裁定方針（裁定者の明示）**: **v2 へ向けた設計段階であり、手戻りを許容して
  最善かつシンプルな構成を採る**（先行2裁定と同一方針）

## 裁定

**accept。** 選択は次のとおり。

| 論点 | 裁定 |
|---|---|
| 軸分離の方式 | **accept（新案 — 既存 enum へ寄せる）** — `worktree_state` を物理状態4値へ縮小し、branch 軸は既存 `branch_audit_state`、PR / 工程軸は既存 `work_unit_state` を使う。**新 enum はゼロ** |
| `finish` × dirty | **accept** — `discard`（`M2-FLT-031`）と同一機構で**退避完了を precondition** とし、退避なしの apply を `BLOCKED` |
| 判定述語 | **accept** — 決定表を設計へ明記し**三者照合の対象に含める** |
| 状態語の表記 | **accept** — **大文字閉集合へ統一**する |

## 1. 軸分離 — 既存 enum へ寄せる（issue 案A の改良）

### 確認済みの欠陥

`FLW-DSN-016.md:92` の `worktree_state` 9値には直交3軸が兄弟として並んでいる。

```
worktree_state = ABSENT, ACTIVE_CLEAN, ACTIVE_DIRTY, PR_OPEN, MERGED_EXACT,
                 REMOTE_ADVANCED, WORKTREE_MISMATCH, ORPHAN, FAILED_RETAINED
```

`FLW-DSN-012.md:89` で `worktree.finish` が許可されるのは **`audited` × `merged-exact`** の行だけである。
したがって「未コミット変更があり、かつ tip が merge 済み」という実運用で普通に起こる状態で、
単一 enum がどちらへ倒れるかが **finish が未コミット作業ごと worktree を削除するか否かを決める**。
同時成立時の優先順位規定は本書に存在せず、判定は非決定である。

到達不能値も機械確認した。`FLW-DSN-012` の写像表に現れる worktree 側の値は
`absent` / `active-clean` / `active-dirty` / `pr-open` / `merged-exact` / `orphan` の6値であり、
**`REMOTE_ADVANCED` / `WORKTREE_MISMATCH` / `FAILED_RETAINED` の3値が到達不能**（`SYN-032` の実測値）。

同表の `failed-retained` 行は worktree 列に `active-dirty/orphan` と**スラッシュで2値**を書いており、
単一 enum では足りていない痕跡が表自身に残っている。

### 採る方式

**分離先の enum は既に存在する。** `FLW-DSN-016.md:93` の `branch_audit_state` が branch 軸そのものであり、
PR / 工程軸は `work_unit_state` が既に持っている。

| 現 `worktree_state` の値 | 実際の軸 | 移す先（既存） |
|---|---|---|
| `MERGED_EXACT` / `REMOTE_ADVANCED` / `ORPHAN` | branch | **`branch_audit_state`**（同名の値が既に存在） |
| `PR_OPEN` | PR / 工程 | **`work_unit_state`**（`PR_DRAFT` / `REVIEW_READY` / `MERGE_READY`） |
| `FAILED_RETAINED` | 工程 | **`work_unit_state`**（同名の値が既に存在） |
| `ABSENT` / `ACTIVE_CLEAN` / `ACTIVE_DIRTY` / `WORKTREE_MISMATCH` | 作業ツリーの物理状態 | `worktree_state` に残す |

確定する `worktree_state`（**9値 → 4値**）:

```
worktree_state = ABSENT, CLEAN, DIRTY, MISMATCH
```

`ACTIVE_` 接頭辞は branch 軸の意味を帯びていたため落とす。

`finish` の許可条件は軸の組合せで曖昧さなく書ける:

```
branch_audit_state == MERGED_EXACT かつ worktree_state == CLEAN
（DIRTY のときは下記 2. の退避 precondition を満たすこと）
```

### issue 案A を採らない理由

案A が新設する `worktree_branch_state`（`ACTIVE` / `MERGED_EXACT` / `REMOTE_ADVANCED` / `ORPHAN`）は
**既存 `branch_audit_state` からの `WORKTREE_IN_USE` 除去にすぎず、実質的な重複**である。
三者照合の対象 namespace が2つ増え、同じ語がさらに多くの namespace へ分散する。

本方式なら新 namespace は増えず、逆に副産物として `FLW-DSN-016.md:152-153` の
「`worktree_state` と `branch_audit_state` に共通して現れる3語は**判定述語を namespace ごとに分離する**」
という規定が**丸ごと不要になる**（重複そのものが消えるため）。

到達不能値も、縮小後は `MISMATCH` の1件だけになる。`FLW-DSN-012` の写像表へ
`MISMATCH` に対応する行を追加して解消する。

## 2. `finish` × dirty — 退避完了を precondition とする

現状、dirty を扱う fixture は `M2-FLT-020`（audit）と `M2-FLT-031`（discard）の2件のみで、
**finish 側の dirty fixture が存在しない**。`FLW-DSN-016` §5 は未コミット作業を「復元できない」と
認識しているにもかかわらず、finish 経路に防御が無い。

`discard` は `SYN-019` への対応として、`freeze-manifest` が dirty / untracked を検出したら
**退避（patch 出力または stash 相当）の完了を precondition** とし、退避なしの apply を
`BLOCKED` にする機構を既に持つ（`FLW-DSN-016.md:604`・`M2-FLT-031`）。

**finish にも同一機構を適用する。** 新規機構は不要で、破壊的 operation 2つの扱いが揃う。
無条件 `BLOCKED` は単純だが、discard と finish で挙動が分かれ、利用者が自力で退避する必要がある。
`MERGED_EXACT` を優先して削除を通す案は、未コミット作業を復元不能な形で失うため採らない。

**finish × dirty の fixture を新設する**（`M2-FLT-031` と対になるもの）。

## 3. 判定述語 — 三者照合の対象に含める

現在の三者照合（設計 ⊆ schema ⊆ 実装）は **enum の値集合しか見ない**ため、
「値は一致するが意味が乖離する」経路が塞がっていない。
operation の許可条件を**軸の組合せによる決定表**として設計へ明記し、照合対象に加える。

実装は `SI-FLW-052` の検査群に含める。

## 4. 状態語の表記 — 大文字閉集合へ統一

`FLW-DSN-016` §2 は大文字閉集合（`ACTIVE_CLEAN` / `MERGED_EXACT`）、
`FLW-DSN-012` の写像表は小文字ハイフン（`active-clean` / `merged-exact`）で書かれている。
`SI-FLW-052` は `FLW-FR-007.md:21` の割れを挙げているが、**同じ割れが設計層にもある**
（本裁定の準備で新たに確認した）。

値の正は §2 にあると `FLW-DSN-012.md:96-97` 自身が宣言しているため、表記も §2 へ寄せる。

- 本裁定の範囲で `FLW-DSN-012` の写像表を大文字へ統一する
- `FLW-FR-007`（要件層）の統一は `SI-FLW-052` へ送る（要件層を三者照合の対象へ含める論点と一体のため）

## 波及と次の作業

改訂対象:

- `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`
  — §2 enum（`worktree_state` の4値化、共通語規定 `:152-153` の削除）・
  §8 recovery matrix・§9 fixture catalog（finish × dirty の追加）・判定述語の決定表
- `plugins/bitz-flow/.spec/design/FLW-DSN-012.md`
  — 状態写像表（大文字統一・`MISMATCH` 行の追加・`failed-retained` 行のスラッシュ解消）

実装区分への波及: **M2-3（create / resume / audit）・M2-5（finish / discard）**。
`FLW-DSN-006` の分類表も追随が必要。

**M0 / M1 で凍結済みの enum namespace には触れない。** `worktree_state` は M2 で新設する
enum であり、縮小の影響は M2 内に閉じる。`work_unit_state` と `branch_audit_state` へは
値を追加しない（移す値はいずれも**既に存在する**）。

**順序制約**: `SI-FLW-052` が「検査の構築を文書修正より先に完了させる」ことを求めている。
本裁定の文書改訂は `SI-FLW-051` の裁定を終え、`SI-FLW-052` の機械検査を構築したのちに着手する。
**本裁定は改訂内容を確定するものであって、改訂の着手を意味しない。**

## 未解決として次へ送る論点

| 論点 | 送り先 |
|---|---|
| `work_unit_state` 12値の遷移関係の定義 | `FLW-DSN-012` 改訂時（写像表の行追加と同時に導出する） |
| 判定述語の三者照合の機械実装 | `SI-FLW-052` |
| `FLW-FR-007`（要件層）の状態語表記の統一 | `SI-FLW-052` |
