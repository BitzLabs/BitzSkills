---
id: SI-FLW-044
raised_by: M2 worktree safety 設計（FLW-REV-011 対応）
target: FLW-CON-006
proposed_change_type: modify
status: accepted
---
- **目的**: `git.delete-remote-branch`（`FLW-DSN-012` により **M2 所属**）の保護が、
  可逆な `git.publish-branch` より弱い。**非可逆な操作のほうが防御が薄い**という
  安全境界の逆転を M2 着手前に是正する。

- **現状の非対称**:

  | operation | 可逆性 | 現行の保護 | 出典 |
  |---|---|---|---|
  | `git.publish-branch` | 可逆（再 push できる） | provider が**原子的に検証する** expected remote OID **CAS**。CAS 非対応 platform は `UNSUPPORTED` | `FLW-DSN-015` |
  | `git.delete-remote-branch` | **非可逆** | 「削除**直前に再照会**し、一致しない場合は削除しない」 | `FLW-CON-006`（approved） |

  「再照会して一致を確認してから削除する」は read-then-delete であり、
  **再照会と delete 要求の間の TOCTOU を構造的に許す**。さらに同一 SHA へ戻す
  force push（ABA）は再照会一致では原理的に検出できない。

  `FLW-REV-011:SYN-007` が worktree-dir について「destructive の防御が
  `git.delete-remote-branch` と同等以下」と指摘しているが、**その基準側である
  `git.delete-remote-branch` 自体が M1 の publish より弱い**。

- **提案する修正**: `FLW-CON-006` の削除条件を CAS へ**厳格化**する（緩和ではない）。

  1. 削除は **provider が原子的に検証する expected-OID 条件付き削除（CAS）でのみ**行う。
     条件なし削除（`git push origin :branch` 相当）は実装・提示ともに禁止する。
  2. expected-OID 条件付き削除を原子的に検証できない platform / protocol では
     `git.delete-remote-branch` を `UNSUPPORTED` とする（publish と同じ縮退規則）。
  3. **ABA 検出**を capability として扱う。「plan 時 snapshot 以降に remote ref の
     更新イベントが観測されていない」ことを provider capability で検出する。
     capability の**実在性は M2 の最初の区分で先に確認**し、実在しなければ分岐を作らず
     「削除は常に ABA 不検出を明示した承認要求を経る」単一経路へ確定させる（死に枝を残さない）。
  4. 削除対象 ref が指す commit が default branch から**到達可能**であることを precondition に含める。
     到達不能なら `BLOCKED`（squash merge で到達性が成立しない場合の
     `FLW-DSN-006` の「差分の見かけだけで削除しない」と同じ結論へ収束させる）。
  5. `FLW-DSN-006` の audit 分類 `REMOTE_ADVANCED`（remote だけが head から進行）の target に対しては、
     **plan の生成自体を `BLOCKED`** にする。

  既存の受入基準（独立 operation として扱い自動連結しない、応答喪失時は旧 plan で再削除せず
  `BLOCKED`、禁止 command 出力 0 件）は**すべて維持**する。

- **対象ファイル**: `plugins/bitz-flow/.spec/requirements/FLW-CON-006.md`（受入基準の厳格化・version bump）、
  M2 詳細設計、`plugins/bitz-flow/.spec/design/FLW-DSN-012.md`（operation contract）。

- **確認観点**:
  - plan 後 apply 前に remote ref が別 SHA へ進んだ fixture で CAS 不成立となり削除されないこと。
  - plan 後 apply 前に force push で**同一 SHA へ戻った**（ABA）fixture で、
    capability がある環境では停止し、ない環境では承認要求が出ること。
  - 条件なし削除の要求が拒否され、CAS 非検証 protocol が `UNSUPPORTED` になること。
  - `REMOTE_ADVANCED` の target に対し plan が生成されないこと。
  - default branch から到達不能な ref の削除が `BLOCKED` になること。
  - 既存の負の fixture（証跡不一致時の削除 0 件、禁止 command 出力 0 件）がそのまま PASS すること。

- **影響推定・ロールバック**: **approved 要件の受入基準を厳格化**するため要件改訂と再承認が必要で
  Design Gate 必須。既存基準を緩めないため現行の負の fixture は影響を受けない。
  M1 operation は変更しない。却下した場合、安全境界の逆転を残したまま M2 出口の
  「finish / discard fault 全通過」を主張することになる。
  なお本件は `SI-FLW-024`（stacked PR 再検分。M4 着手前裁定）とは対象が異なり独立に裁定できる。

- **依存**: `FLW-CON-006`（改訂対象）、`FLW-DSN-015`（remote-write CAS）、
  `FLW-REV-011:SYN-007`（destructive 防御の水準）、`FLW-FR-007`、`FLW-NFR-005`。
  **推薦: accept**。基準となる operation 自体を先に直さないと、
  worktree-dir の防御水準を「`git.delete-remote-branch` と同等以上」と定義できない。
