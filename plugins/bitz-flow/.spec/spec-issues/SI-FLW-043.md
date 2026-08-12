---
id: SI-FLW-043
raised_by: M2 worktree safety 設計（FLW-REV-011 対応）
target: FLW-NFR-007
proposed_change_type: modify
status: open
---
- **目的**: `FLW-NFR-007`（永続 file 更新の原子性と完全性、**approved**）が
  repo 境界外への書き込みを**無条件に禁止**しており、M2 の worktree 実体作成・削除が
  承認済み要件に抵触する。設計補強だけでは閉じないため要件改訂を起票する。

- **現状（approved 要件の受入基準）**:

  > WHEN 対象が symlink、複数 hardlink、**repo 境界外 parent**、または所有者不一致である
  > THEN bitz-flow は原本を変更せず `BLOCKED` を返すこと SHALL

  `FLW-DSN-006` の worktree 配置は `<repo-parent>/.worktrees/...` であり、
  **定義上つねに repo 境界外 parent を持つ**。したがって現行要件のままでは
  M2 の `worktree.create` / `discard` はすべて `BLOCKED` になる。

  同要件はさらに「WHEN filesystem または platform で atomicity と durability を検証できない
  THEN 該当永続 file write を `UNSUPPORTED` にすること SHALL」と定めており、
  worktree root が repo と別 filesystem にある場合は `UNSUPPORTED` 側へ落ちる。

- **提案する修正**: 無条件禁止を**条件付き許可**へ改める。
  「repo 境界外だから拒否」ではなく「**承認済み root 配下だと機械検証できたから許可**」という
  論理へ置き換える。許可条件は次の3点すべてとし、1つでも欠ければ従来どおり `BLOCKED` とする。

  1. canonicalize 後の path が承認済み worktree root 配下にあること
  2. root の外へ escape しないこと（`..` / symlink / bind mount / hardlink / case 差）
  3. `FLW-CON-005` の明示的人間承認を、`FLW-REV-011:GP-002` が求める
     **単回 capability として**得ていること（承認の使い回しを許さない）

  symlink・複数 hardlink・所有者不一致に対する**既存の禁止は緩めない**。
  緩めるのは「repo 境界外 parent」の一項目だけである。

  cross-filesystem 時は durability commit point を「registry entry の atomic 公開完了時点」と
  定義し、実体は registry entry を正として後追い reconcile する（詳細は M2 詳細設計）。

- **対象ファイル**: `plugins/bitz-flow/.spec/requirements/FLW-NFR-007.md`（受入基準の改訂・version bump）、
  M2 詳細設計、`plugins/bitz-flow/skills/flow-core/scripts/flowlib/` の path 検査実装。

- **確認観点**:
  - 承認済み root 配下への write が許可され、root 外への write が引き続き `BLOCKED` になること。
  - symlink・複数 hardlink・所有者不一致の既存 negative fixture が**そのまま PASS** すること
    （改訂で緩んでいないことの確認）。
  - 単回 capability を伴わない worktree write が `BLOCKED` になること。
  - repo 内 file 更新（M1 の intent・ledger）の挙動が変わらないこと。

- **影響推定・ロールバック**: **approved 要件の受入基準変更**であり、設計補強では代替できない。
  軽量レーン不適・Design Gate 必須。M1 operation の target（index / ref）は repo 内・
  同一 filesystem 前提のまま挙動不変。却下した場合は worktree root を repo 配下へ限定する
  縮退が必要になり、`FLW-DSN-006` の「repo 内走査への混入を避けるため repo 外を既定とする」
  判断と両立しないため、配置規則自体の再設計に戻る。

- **依存**: `FLW-REV-011:GP-002`（承認の capability 化）、`FLW-REV-011:GP-010`
  （機械強制層）、`FLW-CON-005`、`FLW-DSN-006`。
  **推薦: accept**。M2 の前提そのものであり、これを閉じないと `worktree.create` を
  設計どおりに実装した時点で要件違反になる。
